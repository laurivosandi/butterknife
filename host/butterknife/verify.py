import sys
import http.client
import os
import re
from butterknife.fssum import generate_manifest

class VerificationError(Exception):
    pass

def verify_manifest(subvolume):
    RE_SUBVOL = "@template:(?P<domain>[\w\d]+(\.[\w\d]+)+)\.([\W\w\d]+):"
    subvol_basename = os.path.basename(subvolume)

    m = re.match(RE_SUBVOL, subvol_basename)
    if not m:
        ValueError("Subvolume %s does not match expression %s" % (subvol_basename, RE_SUBVOL))

    # Derive actual domain name
    namespace, _, _ = m.groups()
    domain = ".".join(reversed(namespace.split(".")))

    # Fetch manifest from the originating server
    print("Streaming https://%s/%s/manifest" % (domain, subvol_basename))
    conn = http.client.HTTPSConnection(domain)
    conn.request("GET", "/%s/manifest" % subvol_basename)
    response = conn.getresponse()

    # Generate manifest for the template subvolume
    local_manifest = generate_manifest(subvolume)

    # Compare local and remote manifest
    for remote_entry in response:
        local_tuple = next(local_manifest)
        local_entry = ("\t".join(["-" if j == None else str(j) for j in local_tuple])+"\n").encode("utf-8")
        if remote_entry != local_entry:
            raise VerificationError("Entries %s and %s don't match." % (local_entry, remote_entry))

