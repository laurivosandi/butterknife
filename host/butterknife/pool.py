
import click
import os
import subprocess
import tempfile
from datetime import datetime
from butterknife.fssum import generate_manifest
from butterknife.subvol import Subvol

BTRFS = "btrfs"
MANIFEST_DIR = "/var/lib/butterknife/manifests"

class LocalPool(object):
    DEFAULT_PATH = "/var/lib/butterknife/pool"

    def __init__(self, path=DEFAULT_PATH):
        self.path = os.path.abspath(path) if path else ''

    def __str__(self):
        return "file://%s" % self.path
        
    def template_list(self, f=None):
        templates = {}
        for s in self.subvol_list():
            if f and not f.match(s):
                continue
            templates[(s.namespace, s.identifier)] = templates.get((s.namespace, s.identifier), set()).union({s.architecture})
            
        for (namespace, identifier), architectures in templates.items():
            yield namespace, identifier, tuple(architectures)

    def subvol_list(self):
        d = self.path or self.DEFAULT_PATH
        return [(Subvol(j,
                signed=os.path.exists(os.path.join(MANIFEST_DIR, j + ".asc")),
                created=datetime.fromtimestamp(int(os.stat(os.path.join(d, j)).st_mtime)))) \
            for j in os.listdir(d) if j.startswith("@template:")]
        
    def receive(self, fh, subvol, parent_subvol=None):
        # TODO: Transfer to temporary directory
        # TODO: Fetch manifest
        # TODO: Verify manifest
        cmd = BTRFS, "receive", os.path.join(self.path), "-C"
        click.echo("Executing: %s" % " ".join(cmd))
        return subprocess.Popen(cmd, bufsize=-1, stdin=fh)

    def send(self, subvol, parent_subvol=None):
        subvol_path = os.path.join(self.path, str(subvol))
        if not os.path.exists(subvol_path):
           raise SubvolNotFound(str(subvol))
        cmd = BTRFS, "send", subvol_path
        if parent_subvol:
            parent_subvol_path = os.path.join(self.path, str(parent_subvol))
            if not os.path.exists(parent_subvol_path):
                raise SubvolNotFound(str(parent_subvol))
            cmd += "-p", parent_subvol_path
        if os.getuid() > 0:
            cmd = ("sudo", "-n") + cmd
        click.echo("Executing2: %s" % " ".join(cmd))
        return subprocess.Popen(cmd, bufsize=-1, stdout=subprocess.PIPE)

    def tar(self, subvol):
        subvol_path = os.path.join(self.path, str(subvol))
        cmd = "tar", "cvf", "-", "."
        if os.getuid() > 0:
            cmd = ("sudo", "-n") + cmd
        click.echo("Executing: %s" % " ".join(cmd))
        return subprocess.Popen(cmd, bufsize=-1, stdout=subprocess.PIPE, cwd=subvol_path)

    def manifest(self, subvol):
        """
        Generator for manifest, yields 7-tuples
        """
        subvol_path = os.path.join(self.path, str(subvol))
        builtin_path = os.path.join(subvol_path, MANIFEST_DIR[1:], str(subvol))
        manifest_path = os.path.join(MANIFEST_DIR, str(subvol))

        if os.path.exists(builtin_path):
            # Stream the manifest written into the (read-only) template,
            # note that this has not been done up to now
            return open(builtin_path, "rb")
        elif os.path.exists(manifest_path):
            # Stream the manifest written into /var/lib/butterknife/manifests
            return open(manifest_path, "rb")
        else:
            # If we don't have any stream manifest and save it under /var/lib/butterknife/manifests
            def generator():
                with tempfile.NamedTemporaryFile(prefix=str(subvol), dir=MANIFEST_DIR, delete=False) as fh:
                    print("Temporarily writing to", fh.name)
                    for entry in generate_manifest(os.path.join(self.path, str(subvol))):
                        line = ("\t".join(["-" if j == None else str(j) for j in entry])).encode("utf-8")+b"\n"
                        fh.write(line)
                        yield line
                    print("Renaming to", manifest_path)
                    os.rename(fh.name, manifest_path)
            return generator()

    def signature(self, subvol):
        """
        Return file object corresponding to signature file
        """
        return open(os.path.join(MANIFEST_DIR, "%s.asc" % subvol), "rb")

