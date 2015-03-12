import subprocess
import os
import falcon
import lxc
import unicodedata
import shutil
import stat
from time import sleep
from util import serialize

def pop_container(func):
    def wrapped(instance, req, resp, name, *args, **kwargs):
        return func(instance, req, resp, lxc.Container(name), *args, **kwargs)
    return wrapped

class ContainerResource(object):
    @serialize
    def on_get(self, req, resp):
        return {"containers": map(lambda name: lxc.Container(name), filter(lambda s:"-template" in s, lxc.list_containers()))}
        
class ContainerDetailResource(object):
    @serialize
    @pop_container
    def on_get(self, req, resp, container):
        du = 0
        for root, dirs, files in os.walk(container.get_config_item("lxc.rootfs")):
            for file in files:
                try:
                    mode, inode, dev, nlink, uid, gid, size, atime, mtime, ctime = os.lstat(os.path.join(root, file))
                    if stat.S_ISREG(mode) and not stat.S_ISLNK(mode):
                        du += size
                except FileNotFoundError:
                    pass
                
        return {
            "name": container.name,
            "disk_usage": du }

class SnapshotResource(object):
    @serialize
    @pop_container
    def on_get(self, req, resp, container):
        print(dir(container))
        def generator():
            for name, comment_filename, timestamp, root in container.snapshot_list():
                if os.path.exists(comment_filename):
                    with open(comment_filename) as fh:
                        comment = fh.read().strip()
                else:
                    comment = None
                yield {
                    "name": name,
                    "comment": comment or "",
                    "timestamp": timestamp }
        return { "snapshots": sorted(generator(), reverse=True, key=lambda j:int(j["name"][4:]))}

class StreamingResource(object):
    @pop_container
    def on_get(self, req, resp, container, snap):
        sources = req.get_param("src")
        suggested_filename = container.name + "_snapshot_" + snap
        if sources:
            suggested_filename += "_from_" + sources.replace(",", "_")
        suggested_filename += ".far"

        path = os.path.join("/var/lib/lxcsnaps", container.name, snap, "rootfs-ro")
        resp.set_header("Content-Disposition", "attachment; filename=\"%s\"" % suggested_filename)
        resp.set_header('Content-Type', 'application/btrfs-stream')
        resp.set_header('Content-Encoding', 'gzip')
        cmd = "/sbin/btrfs", "send", path
        print("SOURCES:", sources)
        if sources:
            for source in sources.split(","):
                print("parsing:", source)
                if not source:
                    continue
                cmd += ("-c", os.path.join("/var/lib/lxcsnaps", container.name, source, "rootfs-ro") )
        print("Executing:", " ".join(cmd))
        streamer = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        cmd = "/usr/bin/pigz", "--best",
        compressor = subprocess.Popen(cmd, stdin=streamer.stdout, stdout=subprocess.PIPE)
        resp.stream = compressor.stdout
        


app = falcon.API()
app.add_route("/api/container/", ContainerResource())
app.add_route("/api/container/{name}/", ContainerDetailResource())
app.add_route("/api/container/{name}/snapshot/", SnapshotResource())
app.add_route("/api/container/{name}/snapshot/{snap}/stream/", StreamingResource())

if __name__ == '__main__':
    from wsgiref import simple_server
    httpd = simple_server.make_server('0.0.0.0', 80, app)
    httpd.serve_forever()

