
class SubvolNotFound(Exception):
    pass

class Subvol(object):
    def __init__(self, subvol):
        if "/" in subvol:
            raise Exception("Invalid subvolume base name, contains /")
        self.category, fqn, self.architecture, self.version = subvol.split(":")
        self.namespace, self.identifier = fqn.rsplit(".", 1)
        assert self.version.startswith("snap")
        self.numeric_version = int(self.version[4:])

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
        
