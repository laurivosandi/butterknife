
import subprocess
import os
import unicodedata
import json
import falcon
from datetime import date, datetime
from butterknife.pool import Subvol

class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        if isinstance(obj, map):
            return tuple(obj)
        if isinstance(obj, Subvol):
            return obj.version
        return json.JSONEncoder.default(self, obj)

def parse_subvol(func):
    def wrapped(instance, req, resp, subvol, *args, **kwargs):
        return func(instance, req, resp, Subvol("@" + subvol), *args, **kwargs)
    return wrapped

def serialize(func):
    """
    Falcon response serialization
    """
    def wrapped(instance, req, resp, **kwargs):
        assert not req.get_param("unicode") or req.get_param("unicode") == u"✓", "Unicode sanity check failed"
        resp.set_header("Cache-Control", "no-cache, no-store, must-revalidate");
        resp.set_header("Pragma", "no-cache");
        resp.set_header("Expires", "0");
        r = func(instance, req, resp, **kwargs)
        if not resp.body:
            if not req.client_accepts_json:
                raise falcon.HTTPUnsupportedMediaType(
                    'This API only supports the JSON media type.',
                    href='http://docs.examples.com/api/json')
            resp.set_header('Content-Type', 'application/json')
            resp.body = json.dumps(r, cls=MyEncoder)
        return r
    return wrapped
    

from jinja2 import Environment, PackageLoader, FileSystemLoader
env = Environment(loader=PackageLoader('butterknife', 'templates'))

def templatize(path):
    template = env.get_template(path)
    def wrapper(func):
        def wrapped(instance, req, resp, **kwargs):
            assert not req.get_param("unicode") or req.get_param("unicode") == u"✓", "Unicode sanity check failed"

            r = func(instance, req, resp, **kwargs)

            if not resp.body:
                if  req.get_header("Accept") == "application/json":
                    resp.set_header("Cache-Control", "no-cache, no-store, must-revalidate");
                    resp.set_header("Pragma", "no-cache");
                    resp.set_header("Expires", "0");
                    resp.set_header('Content-Type', 'application/json')
                    resp.body = json.dumps(r, cls=MyEncoder)
                    return r
                else:
                    resp.set_header('Content-Type', 'text/html')
                    resp.body = template.render(request=req, **r)
                    return r
        return wrapped
    return wrapper
    
class PoolResource(object):
    def __init__(self, pool, subvol_filter):
        self.pool = pool
        self.subvol_filter = subvol_filter

class SubvolResource(PoolResource):
    @templatize("index.html")
    def on_get(self, req, resp):
        def subvol_generator():
            for j in sorted(self.pool.subvol_list(), reverse=True):
                if req.get_param("architecture"):
                    if req.get_param("architecture") != j.architecture:
                        continue
                yield {
                    "path": str(j),
                    "namespace": j.namespace,
                    "identifier": j.identifier,
                    "architecture": j.architecture,
                    "version": j.version }

        return { "subvolumes": tuple(subvol_generator()) }

class TemplateResource(PoolResource):
    @serialize
    def on_get(self, req, resp):
        return {"templates": map(
            lambda j:{"namespace": j[0], "identifier":j[1], "architectures":j[2]},
            self.pool.template_list(self.subvol_filter))}

class VersionResource(PoolResource):
    @serialize
    def on_get(self, req, resp, name, arch):
        namespace, identifier = name.rsplit(".", 1)
        subset_filter = self.subvol_filter.subset(namespace=namespace,
            identifier=identifier, architecture=arch)
        return { "versions": map(
            lambda v:{"identifier":v},
            sorted(subset_filter.apply(self.pool.subvol_list()), reverse=True, key=lambda j:j.numeric_version)) }

class LegacyStreamingResource(PoolResource):
    def on_get(self, req, resp, name, arch, version):

        parent_version = req.get_param("parent")
        
        subvol = "@template:%(name)s:%(arch)s:%(version)s" % locals()
        if not self.subvol_filter.match(Subvol(subvol)):
            raise Exception("Not going to happen")
        
        suggested_filename = "%(name)s:%(arch)s:%(version)s" % locals()
        if parent_version:
            parent_subvol = "@template:%(name)s:%(arch)s:%(parent_version)s" % locals()
            if not self.subvol_filter.match(Subvol(parent_subvol)): raise
            suggested_filename += ":" + parent_version
        else:
            parent_subvol = None
        suggested_filename += ".far"

        resp.set_header("Content-Disposition", "attachment; filename=\"%s\"" % suggested_filename)
        resp.set_header('Content-Type', 'application/btrfs-stream')

        streamer = self.pool.send(subvol, parent_subvol)
        resp.stream = streamer.stdout

        accepted_encodings = req.get_header("Accept-Encoding") or ""
        accepted_encodings = [j.strip() for j in accepted_encodings.lower().split(",")]

        if "gzip" in accepted_encodings:
            for cmd in "/usr/bin/pigz", "/bin/gzip":
                if os.path.exists(cmd):
                    resp.set_header('Content-Encoding', 'gzip')
                    print("Compressing with %s" % cmd)
                    compressor = subprocess.Popen((cmd,), stdin=streamer.stdout, stdout=subprocess.PIPE)
                    resp.stream = compressor.stdout
                    break
            else:
                print("No gzip compressors found, falling back to no compression")
        else:
            print("Client did not ask for compression")

class StreamResource(PoolResource):
    @parse_subvol
    def on_get(self, req, resp, subvol):
        if not self.subvol_filter.match(subvol):
            resp.body = "Subvolume does not match filter"
            resp.status = falcon.HTTP_403
            return

        parent_slug = req.get_param("parent")
        suggested_filename = "%s.%s-%s-%s" % (subvol.namespace, subvol.identifier, subvol.architecture, subvol.version)

        if parent_slug:
            parent_subvol = Subvol(parent_slug) if parent_slug else None
            if not self.subvol_filter.match(parent_subvol):
                resp.body = "Subvolume does not match filter"
                resp.status = falcon.HTTP_403
                return
            suggested_filename += "-" + parent_subvol.version
        else:
            parent_subvol = None

        suggested_filename += ".far"

        resp.set_header("Content-Disposition", "attachment; filename=\"%s\"" % suggested_filename)
        resp.set_header('Content-Type', 'application/btrfs-stream')

        try:
            streamer = self.pool.send(subvol, parent_subvol)
        except SubvolNotFound as e:
            resp.body = "Could not find subvolume %s\n" % str(e)
            resp.status = falcon.HTTP_403
            return
        resp.stream = streamer.stdout

        accepted_encodings = req.get_header("Accept-Encoding") or ""
        accepted_encodings = [j.strip() for j in accepted_encodings.lower().split(",")]

        if "gzip" in accepted_encodings:
            for cmd in "/usr/bin/pigz", "/bin/gzip":
                if os.path.exists(cmd):
                    resp.set_header('Content-Encoding', 'gzip')
                    print("Compressing with %s" % cmd)
                    compressor = subprocess.Popen((cmd,), stdin=streamer.stdout, stdout=subprocess.PIPE)
                    resp.stream = compressor.stdout
                    break
            else:
                print("No gzip compressors found, falling back to no compression")
        else:
            print("Client did not ask for compression")


