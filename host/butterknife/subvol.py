from datetime import datetime
import os

def determine_rootfs_subvol():
    for row in open("/proc/%d/mountinfo" % os.getpid()):
        mid, pid, devid, root, mpoint, mopts, opt, sep, fs, msource = row.strip().split(" ", 9)
        if mpoint == "/":
            if root.startswith("/@root:"):
                return "@template:" + root[7:]
            break
    return None

class SubvolNotFound(Exception):
    pass

class Subvol(object):
    def __init__(self, subvol, signed=False, created=None):
        if "/" in subvol:
            raise Exception("Invalid subvolume base name, contains /")
        self.category, fqn, self.architecture, self.version = subvol.split(":")
        self.namespace, self.identifier = fqn.rsplit(".", 1)
        self.numeric_version = int(self.version[4:]) if self.version.startswith("snap") else int(self.version)
        self.signed = signed
        self.created = created if self.version.startswith("snap") else datetime.strptime(self.version, "%Y%m%d%H%M%S")

    @property
    def domain(self):
        return ".".join(reversed(self.namespace.split(".")))

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "%s:%s.%s:%s:%s" % (self.category, self.namespace, self.identifier, self.architecture, self.version)

    def __eq__(self, other):
        return repr(self) == repr(other)

    def __gt__(self, other):
        return (self.namespace, self.identifier, self.architecture, self.numeric_version) > \
            (other.namespace, other.identifier, other.architecture, other.numeric_version)

    def __lt__(self, other):
        return other > self

    def __hash__(self):
        return hash(repr(self))
        
