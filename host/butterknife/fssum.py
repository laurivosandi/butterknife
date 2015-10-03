import os
import hashlib
import stat

# Inspired by fssum from Arne's far-progs:
# https://kernel.googlesource.com/pub/scm/linux/kernel/git/arne/far-progs/+/master/fssum.c

def symbolic_notation(path):
    # TODO: Assert no ACL-s, SELinux context or extended attributes are present

    attribs = os.lstat(path)
    mode = attribs.st_mode
    # Derived from /usr/include/bits/stat.h
    m = "?fc?d?b?-?l?s?"[mode >> 12]
    m += "-r"[mode >> 8 & 1]
    m += "-w"[mode >> 7 & 1]
    m += "-xSs"[mode >> 6 & 1 | mode >> 10 & 2]
    m += "-r"[mode >> 5 & 1]
    m += "-w"[mode >> 4 & 1]
    m += "-xSs"[mode >> 3 & 1 | mode >> 9 & 2]
    m += "-r"[mode >> 2 & 1]
    m += "-w"[mode >> 1 & 1]
    m += "-xTt"[mode & 1 | mode >> 8 & 2]
    return m, str(attribs.st_uid), str(attribs.st_gid)

def generate_manifest(target, relroot=""):
    # Generate manifest function recursively traverses target path and
    # yields tuples of:
    # 1. Symbolic notation, eg "drwxr-xr-x"
    # 2. Owner ID, eg "0"
    # 3. Group ID, eg "0"
    # 4. Checksum algorithm, eg "sha256"
    # 5. Checksum, eg "9b6287917439911fda0933c95e85d78a34b1068c5a58f1041b8ca3576f238dc6"
    # 6. Filename, eg "/usr/bin/sudo"
    # 7. Symlink target if any, eg "-"

    absroot = os.path.join(target, relroot)
    assert "\t" not in absroot

    # os.walk puts symlinks to dirs list if the symlink refers to directory
    # even if followlinks is set False, this is NONSENSE.
    # Also sorting os.walk is troublesome.

    dirs = []
    for filename in sorted(os.listdir(absroot)):
        assert "\t" not in filename
        abspath = os.path.join(absroot, filename)
        relpath = os.path.join("/", relroot, filename)
        bitmap, uid, gid = symbolic_notation(abspath)

        if bitmap[0] == "-":
            buf = open(abspath, "rb").read()
            j = os.stat(abspath)
            m = hashlib.sha256()
            m.update(buf)
            m.hexdigest()
            yield bitmap, uid, gid, "sha256", m.hexdigest(), relpath, None
        elif bitmap[0] == "l":
            yield bitmap, uid, gid, None, None, relpath, os.readlink(abspath)
        elif bitmap[0] == "d":
            dirs.append((filename, abspath, relpath, bitmap, uid, gid))
        else:
            yield bitmap, uid, gid, None, None, relpath, None

    for dirname, abspath, relpath, bitmap, uid, gid in dirs:
        yield bitmap, uid, gid, None, None, relpath, None
        for entry in generate_manifest(target, os.path.join(relroot, dirname)):
            yield entry

