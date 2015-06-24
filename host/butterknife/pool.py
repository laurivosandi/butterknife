
import os
import click
import subprocess
from butterknife.subvol import Subvol

BTRFS = "/usr/bin/btrfs"

class LocalPool(object):
    DEFAULT_PATH = "/var/butterknife/pool"

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
        return [Subvol(j) for j in os.listdir(self.path or self.DEFAULT_PATH) if j.startswith("@template:")]
        
    def receive(self, fh, subvol, parent_subvol=None):
        # TODO: Transfer to temporary directory
        cmd = BTRFS, "receive", os.path.join(self.path), "-C"
#        if parent_subvol:
#            cmd += "-p", "/" + str(parent_subvol)
        click.echo("Executing: %s" % " ".join(cmd))
        return subprocess.Popen(cmd, stdin=fh, close_fds=True)

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
        click.echo("Executing: %s" % " ".join(cmd))
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, close_fds=True)

