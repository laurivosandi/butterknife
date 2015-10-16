import sys
import http.client
import os
import re
import subprocess
import tempfile
from butterknife.fssum import generate_manifest

TRUSTED_PATH = "/etc/butterknife/trusted.gpg.d"

class VerificationError(Exception):
    pass

def verify_manifest(subvolume):

    def urlopen(hostname, path):
        conn = http.client.HTTPConnection(domain)
        conn.request("GET", path)
        response = conn.getresponse()

        # Determine if we had HTTP -> HTTPS redirect
        if response.status == 302:
            response.read()
            redirect = response.headers.get("Location")
            if redirect != "https://" + hostname + path:
                raise VerificationError("Not allowed redirect to %s, would allow https://%s%s" % (redirect, hostname, path))
            conn = http.client.HTTPSConnection(domain)
            conn.request("GET", path)
            response = conn.getresponse()

        return response

    RE_SUBVOL = "@template:(?P<domain>[\w\d]+(\.[\w\d]+)+)\.([\W\w\d]+):"
    subvol_basename = os.path.basename(subvolume)

    m = re.match(RE_SUBVOL, subvol_basename)
    if not m:
        raise ValueError("Subvolume %s does not match expression %s" % (repr(subvol_basename), RE_SUBVOL))

    # Derive actual domain name
    namespace, _, _ = m.groups()
    domain = ".".join(reversed(namespace.split(".")))

    # Derive file paths
    manifest_path = os.path.join("/var/lib/butterknife/manifests", subvol_basename)
    signature_path = manifest_path + ".asc"
    keyring_path = os.path.join(TRUSTED_PATH, domain.replace(".", "_") + ".gpg")

    if not os.path.exists(keyring_path):
        print("Fetch keyring from http://%s/keyring.gpg" % domain)
        if not os.path.exists(TRUSTED_PATH):
            print("Creating directory", TRUSTED_PATH)
            os.makedirs(TRUSTED_PATH)

        response = urlopen(domain, "/keyring.gpg")

        if response.status == 200:
            with tempfile.NamedTemporaryFile(dir=TRUSTED_PATH, prefix=".", delete=False) as fh:
                print("Writing keyring to file %s" % fh.name)
                fh.write(response.read())
                print("Moving", fh.name, "to", keyring_path)
                os.rename(fh.name, keyring_path)
        else:
            raise VerificationError("Failed to fetch keyring from http://%s/keyring.gpg, server responded %d" % (domain, response.status))
    else:
        print("Using keyring", keyring_path)


    if os.path.exists(signature_path):
        # Signature is already present locally, assume it's valid
        sfh = None
        print("Found signature in %s" % signature_path)
    else:
        # Otherwise attempt to fetch signature from origin
        print("Fetching signature from http://%s/%s/signature" % (domain, subvol_basename))
        response = urlopen(domain, "/%s/signature" % subvol_basename)

        if response.status != 200:
            raise VerificationError(response.read().decode("ascii"))
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(signature_path), prefix=".", delete=False) as sfh:
            print("Writing signature to file %s" % sfh.name)
            sfh.write(response.read())

    if os.path.exists(manifest_path):
        # Manifest is already present locally, assume it's valid
        print("Found manifest in", manifest_path)
        response = open(manifest_path, "rb")
        mfh = None
    else:
        # Fetch manifest from the origin
        print("Streaming http://%s/%s/manifest" % (domain, subvol_basename))
        response = urlopen(domain, "/%s/manifest" % subvol_basename)
        mfh = tempfile.NamedTemporaryFile(dir=os.path.dirname(manifest_path), prefix=".", delete=False)

    # Read manifest from stdin line by line
    cmd = "gpgv", "--keyring", keyring_path, sfh.name if sfh else signature_path, "-"
    print("Invoking in the background:", " ".join(cmd))

    # Generate manifest for the template subvolume
    print("Recursing over:", subvolume)
    local_manifest = generate_manifest(subvolume)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    # Compare local and remote manifest
    for remote_entry in response:
        local_tuple = next(local_manifest)
        local_entry = ("\t".join(["-" if j == None else str(j) for j in local_tuple])+"\n").encode("utf-8")
        if remote_entry != local_entry:
            raise VerificationError("Entries %s and %s don't match." % (local_entry, remote_entry))
        proc.stdin.write(remote_entry)
        if mfh:
            mfh.write(remote_entry)

    # Ensure that local manifest has no extra lines compared to remote one
    for local_tuple in local_manifest:
        raise VerificationError("Local manifest has excessive lines")

    # Wait GPG to finish
    proc.communicate()
    if proc.returncode != 0:
        raise VerificationError("GPG returned exit code %d" % proc.returncode)

    # If verification was successful, move signature
    if sfh:
        os.rename(sfh.name, signature_path)

    # If manifest wasn't present locally, move it as well
    if mfh:
        os.rename(mfh.name, manifest_path)
