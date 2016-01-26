
import os
import subprocess
from butterknife.pool import LocalPool
from butterknife.subvol import Subvol

class SecureShellPool(LocalPool):
    def __init__(self, hostname, port=None, path=None, user=None):
        self.hostname = hostname
        self.port = port 
        self.user = user
        self.path = path or "/var/lib/butterknife/pool/"
                
    def __str__(self):
        url = "ssh://"
        if self.user:
            url += "%s@" % self.user
        url += self.hostname
        if self.port:
            url += ":%d" % self.port
        if self.path != "/var/lib/butterknife/pool/":
            url += self.path
        return url
        
    def subvol_list(self):
        return [Subvol(j) for j in subprocess.check_output(self.prefix() + ("ls", self.path)).decode("utf-8").split("\n") if j.startswith("@template:")]
        
    def prefix(self):
        cmd = "ssh",
        if self.port:
            cmd += "-p", self.port
        if self.user:
            return cmd + (self.user + "@" + self.hostname,)
        return cmd + (self.hostname,)

    def receive(self, fh, subvol, parent_subvol=None):
        cmd = self.prefix() + "btrfs", "receive", os.path.join(self.path), "-C"
        if parent_subvol:
            cmd += "-p", "/" + str(parent_subvol)
        return subprocess.Popen(cmd, stdin=fh)

    def send(self, subvol, parent_subvol=None):
        cmd = self.prefix() + ("btrfs", "send", os.path.join(self.path, str(subvol)))
        if parent_subvol:
            cmd += "-p", os.path.join(self.path, str(parent_subvol))
        return subprocess.Popen(cmd, stdout=subprocess.PIPE)

    def manifest(self, subvol):
        raise NotImplementedError("Generating manifest for remote pool not implemented, yet!")
