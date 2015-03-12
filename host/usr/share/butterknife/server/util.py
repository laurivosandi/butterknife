# encoding: utf-8
import falcon
import json
import re
import os
import unicodedata
import lxc
from datetime import datetime, date
    
class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z"
        if isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        if isinstance(obj, lxc.Container):
            description_path = os.path.join(os.path.dirname(obj.config_file_name), "description")
            return {
                "description": open(description_path).readline().strip() if os.path.exists(description_path) else "",
                "name": obj.name,
                "ips": obj.get_ips(),
                "running": obj.init_pid if obj.running else False,
                "arch": obj.get_config_item("lxc.arch")}
        if isinstance(obj, map):
            return tuple(obj)
        return json.JSONEncoder.default(self, obj)

def serialize(func):
    """
    Falcon response serialization
    """
    def wrapped(instance, req, resp, **kwargs):
        assert not req.get_param("unicode") or req.get_param("unicode") == u"✓", "Unicode sanity check failed"
        
        # Default to no caching of API calls
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
        
    # Pipe API docs
    wrapped._apidoc = getattr(func, "_apidoc", {})
    wrapped.__doc__ = func.__doc__
    return wrapped


