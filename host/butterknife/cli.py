
import os
import click
from urllib.parse import urlparse
import json
import urllib.request
import configparser
import subprocess
from butterknife.pool import LocalPool
from butterknife.subvol import Subvol

def pool_factory(url):
    o = urlparse(url)
    if o.scheme == "file":
        from butterknife.pool import LocalPool
        assert not o.netloc, "Username, hostname or port not supported for file:// transport"
        assert not o.password
        assert not o.fragment
        assert not o.query
        return LocalPool(o.path)
    if o.scheme in ("http", "https"):
        from butterknife.transport.http import WebPool
        return WebPool(o.hostname, o.port, o.path, secure=o.scheme=="https")
    if o.scheme == "ssh":
        from butterknife.transport.ssh import SecureShellPool
        return SecureShellPool(o.hostname, o.port, o.path, o.username)

def push_pull(source, destination, subvol):
    subvol_filter = Filter(subvol)
    for namespace, identifier, architectures in source.template_list(subvol_filter):
        for architecture in architectures:
            click.echo("Processing %s.%s:%s" % (namespace, identifier, architecture))
            subset_filter = subvol_filter.subset(
                namespace=namespace, identifier=identifier, architecture=architecture)
                
            source_subvols = sorted(subset_filter.apply(source.subvol_list()))
            destination_subvols = sorted(subset_filter.apply(destination.subvol_list()))

            click.echo("%d subvolumes at %s" % (len(source_subvols), source))
            click.echo("%d subvolumes at %s" % (len(destination_subvols), destination))
            
            common_subvols = set(source_subvols).intersection(set(destination_subvols))

            if common_subvols:
                parent_subvol = sorted(common_subvols)[-1]
                click.echo("Last common subvol is: %s" % parent_subvol)
                following_subvols = tuple(filter(lambda subvol: subvol.numeric_version > parent_subvol.numeric_version, source_subvols))
                click.echo("Neet to get %d subvolumes" % len(following_subvols))
            else:
                parent_subvol = None
                following_subvols = source_subvols
                click.echo("No shared subvolumes!")
               

            if not following_subvols:
                click.echo("All versions of %s.%s:%s synchronized, skipping!" % (namespace, identifier, architecture))
                continue

            for subvol in following_subvols:
                if parent_subvol:
                    click.echo("Fetching incremental snapshot %s relative to %s" % (subvol.version, parent_subvol.version))
                else:
                    click.echo("Fetching full snapshot %s" % subvol.version)
                btrfs_send = source.send(subvol, parent_subvol)
                pv = subprocess.Popen(("pv",), stdin=btrfs_send.stdout, stdout=subprocess.PIPE, close_fds=True)
                btrfs_receive = destination.receive(pv.stdout, subvol, parent_subvol)
                btrfs_receive.communicate()
                if btrfs_receive.returncode or btrfs_send.returncode or pv.returncode:
                    exit(255)
                parent_subvol = subvol


@click.command(help="Pull subvolumes")
@click.argument("pool")
@click.option("-s", "--subvol", default="@template:*.*:*:*", help="Subvolume filter")
def pull(pool, subvol):
    click.echo("Pulling %s from %s to local pool" % (subvol, pool))
    push_pull(pool_factory(pool), LocalPool(), subvol)

@click.command(help="Push subvolumes")
@click.argument("pool")
@click.option("-s", "--subvol", default="@template:*.*:*:*", help="Subvolume filter")
def push(pool, subvol):
    click.echo("Pushing %s from local pool to %s" % (subvol, pool))
    push_pull(LocalPool(), pool_factory(pool), subvol)

@click.command(help="List local or remote subvolumes")
@click.argument("pool", default="file://")
@click.option("--subvol", default="@template:*.*:*:*", help="Subvolume filter")
def list(subvol, pool):
    click.echo("Listing %s in %s" % (subvol, pool))
    pool = pool_factory(pool)
    for template in Filter(subvol).apply(pool.subvol_list()):
        click.echo("%s%s" % (pool, template))
        
        
class Filter(object):
    def __init__(self, pattern="@template:*.*:*:*"):
        self.category, name, self.architecture, self.version = pattern.split(":")
        self.namespace, self.identifier = name.rsplit(".", 1)

    def match(self, subvol):
        if self.category != "*" and self.category != subvol.category:
#            print("Category %s fails filter %s" % (self.category, subvol.category))
            return False
        if self.namespace != "*" and self.namespace != subvol.namespace:
#            print("Namespace %s fails filter %s" % (self.namespace, subvol.namespace))
            return False
        if self.identifier != "*" and self.identifier != subvol.identifier: # TODO: specify ,
#            print("Identifier %s fails filter %s" % (self.identifier, subvol.identifier))
            return False
        if self.architecture != "*" and self.architecture != subvol.architecture: # TODO: specify ,
#            print("Architecture %s fails filter %s" % (self.architecture, subvol.architecture))
            return False
        if self.version != "*" and self.version != subvol.version: # TODO: specify , and  -
#            print("Version %s fails filter %s" % (self.version, subvol.version))
            return False
        return True

    def apply(self, iterable):
        for i in iterable:
            if self.match(i):
                yield i
                
    def subset(self, namespace="*", identifier="*", architecture="*", version="*"):
        return Filter(
            "%s:%s.%s:%s:%s" % (
                self.category,
                self.namespace if namespace == "*" else namespace,
                self.identifier if identifier == "*" else identifier,
                self.architecture if architecture == "*" else architecture,
                self.version if version == "*" else version))

@click.command("serve", help="Run built-in HTTP server")
@click.argument("subvol", default="@template:*.*:*:*")
@click.option("-u", "--user", default=None, help="Run as user")
@click.option("-p", "--port", default=80, help="Listen port")
@click.option("-l", "--listen", default="0.0.0.0", help="Listen address")
def serve(subvol, user, port, listen):
    subvol_filter = Filter(subvol)
    pool = LocalPool()
    click.echo("Serving %s from %s at %s:%d" % (subvol, pool, listen, port))
    from butterknife.api import TemplateResource, VersionResource, LegacyStreamingResource, SubvolResource, StreamResource
    import pwd
    import falcon
    from wsgiref.simple_server import make_server, WSGIServer
    from socketserver import ThreadingMixIn

    class ThreadingWSGIServer(ThreadingMixIn, WSGIServer): 
        pass
    print("Listening on %s:%d" % (listen, port))
    
    app = falcon.API()
    app.add_route("/api/template/", TemplateResource(pool, subvol_filter))
    app.add_route("/api/template/{name}/arch/{arch}/version/", VersionResource(pool, subvol_filter))
    app.add_route("/api/template/{name}/arch/{arch}/version/{version}/stream/", LegacyStreamingResource(pool, subvol_filter))
    app.add_route("/api/subvol/", SubvolResource(pool, subvol_filter))
    app.add_route("/api/subvol/@{subvol}/", StreamResource(pool, subvol_filter))
    app.add_route("/", SubvolResource(pool, subvol_filter))
    app.add_route("/@{subvol}/", StreamResource(pool, subvol_filter))
    httpd = make_server(listen, port, app, ThreadingWSGIServer)
    if user:
        _, _, uid, gid, gecos, root, shell = pwd.getpwnam(user)
        sudoer = os.path.join("/etc/sudoers.d", user)

        if uid == 0:
            print("Please specify unprivileged user, eg 'butterknife'")
            exit(254)
        elif not os.path.exists(sudoer):
            print("Please create %s with following content: %s ALL=(ALL) NOPASSWD: /usr/bin/btrfs send /var/butterknife/pool/@template\\:*" % (sudoer, user))
            exit(253)

        print("Switching to user %s (uid=%d, gid=%d)" % (user, uid, gid))
        os.setgid(gid)
        os.setuid(uid)
    elif os.getuid() == 0:
        click.echo("Warning: running as root, this is not reccommended!")
    httpd.serve_forever()

@click.command("receive", help="Receive subvolume over multicast")
@click.option("--pool", default="file:///var/butterknife/pool", help="Remote or local pool")
def multicast_receive(pool):
    cmd = "udp-receiver", "--nokbd"
    udpcast = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    pool = pool_factory(pool)
    pool.receive(udpcast.stdout)
    udpcast.wait()

@click.command("send", help="Send subvolume over multicast")
@click.argument("subvol")
@click.option("--pool", default="file:///var/butterknife/pool", help="Remote or local pool")
@click.option("-m", "--min-wait", default=5, help="Wait until t seconds since first receiver connection has passed")
def multicast_send(subvol, pool, min_wait):
    pool = pool_factory(pool)
    btrfs = pool.send(subvol)
    cmd = "udp-sender", "--nokbd", "--no-progress", "--min-receivers", "1", "--min-wait", str(min_wait)
    udpcast = subprocess.Popen(cmd, stdin=btrfs.stdout)
    btrfs.wait()
    
@click.command("release", help="Snapshot a LXC container and release as Butterknife template")
@click.argument("name")
def lxc_release(name):

    config = configparser.ConfigParser()
    config.read('/etc/butterknife/butterknife.conf')
   

    import lxc
    container=lxc.Container(name)
    if container.running:
        print("Stopping container")
        container.stop()

    ROOTFS = container.get_config_item("lxc.rootfs")
    assert os.path.isdir(ROOTFS), "No directory at %s" % ROOTFS

    POSTDEPLOY_SCRIPTS = os.path.join(ROOTFS, "etc", "butterknife", "postdeploy.d")
    assert os.path.isdir(POSTDEPLOY_SCRIPTS), "Postinstall scripts directory %s missing!" % POSTDEPLOY_SCRIPTS

    config.read(os.path.join(ROOTFS, "etc/butterknife/butterknife.conf"))
    if "template" not in config.sections():
        config.add_section("template")
    if "name" not in config["template"]:
        config.set("template", name)
    config.set("template", "endpoint", config.get("global", "endpoint"))
    config.set("template", "namespace", config.get("global", "namespace"))
    
    architecture = container.get_config_item("lxc.arch")
    config.set("template", "architecture", architecture)

    snapshot = container.snapshot()

    config.set("template", "version", snapshot)

    print("Created snapshot:", snapshot)

    snapdir = os.path.join("/var/lib/lxcsnaps", name, snapshot)

    cmd = "chroot", os.path.join(snapdir, "rootfs"), "/usr/local/bin/butterknife-prerelease"

    print("Executing:", " ".join(cmd))

    import subprocess
    subprocess.call(cmd)

    with open(os.path.join(snapdir, "rootfs/etc/butterknife/butterknife.conf"), "w") as fh:
        config.write(fh)

    cmd = "btrfs", "subvolume", "snapshot", "-r", os.path.join(snapdir, "rootfs"), \
        "/var/butterknife/pool/@template:%(namespace)s.%(name)s:%(architecture)s:%(version)s" % config["template"]

    print("Executing:", " ".join(cmd))
    subprocess.call(cmd)
    
@click.command("list", help="Linux Containers that have been prepared for Butterknife")
def lxc_list():
    import lxc
    for name in lxc.list_containers():
        container=lxc.Container(name)
        rootfs = container.get_config_item("lxc.rootfs")
        
        template_config = os.path.join(rootfs, "etc/butterknife/butterknife.conf")
        if not os.path.exists(template_config):
            continue

        config = configparser.ConfigParser()
        config.read('/etc/butterknife/butterknife.conf')
        config.read(template_config)
        if "template" not in config.sections():
            config.add_section("template")
        if "name" not in config["template"]:
            config.set("template", "name", "?")
        click.echo("%s --> @template:%s:%s:%s" % (name.ljust(40), config.get("global", "namespace"), config.get("template", "name"), container.get_config_item("lxc.arch")))

@click.command("clean", help="Clean incomplete transfers")
def pool_clean():
    for path in os.listdir("/var/butterknife/pool"):
        if not path.startswith("@template:"):
            continue
        try:
            open(os.path.join("/var/butterknife/pool", path, ".test"), "w")
        except OSError as e:
            if e.errno == 30: # This is read-only, hence finished
                continue
        cmd = "btrfs", "subvol", "delete", os.path.join("/var/butterknife/pool", path)
        click.echo("Executing: %s" % " ".join(cmd))
        subprocess.check_output(cmd)

@click.command("release", help="Release systemd namespace as Butterknife template")
@click.argument("name")
def nspawn_release(name):
    config = configparser.ConfigParser()
    config.read('/etc/butterknife/butterknife.conf')
    
    click.echo("Make sure that your nspawn container isn't running!")

    ROOTFS = os.path.join("/var/lib/machines", name)
    assert os.path.isdir(ROOTFS), "No directory at %s" % ROOTFS

    POSTDEPLOY_SCRIPTS = os.path.join(ROOTFS, "etc", "butterknife", "postdeploy.d")
    assert os.path.isdir(POSTDEPLOY_SCRIPTS), "Postinstall scripts directory %s missing!" % POSTDEPLOY_SCRIPTS

    config.read(os.path.join(ROOTFS, "etc/butterknife/butterknife.conf"))
    if "template" not in config.sections():
        config.add_section("template")
    if "name" not in config["template"]:
        config.set("template", name)
    config.set("template", "endpoint", config.get("global", "endpoint"))
    config.set("template", "namespace", config.get("global", "namespace"))
    
    import subprocess
    architecture = subprocess.check_output(("file", os.path.join(ROOTFS, 'bin/bash'))).decode()
    if "32-bit" in architecture:
        architecture = "x86"
    else:
        architecture = "x86_64"
    config.set("template", "architecture", architecture)

    
    pool = pool_factory("file://")
    snapshot = sorted(Filter("@template:%(namespace)s.%(name)s:%(architecture)s:*" % config["template"]).apply(pool.subvol_list()))[-1].numeric_version
    snapshot = "snap"+str(snapshot+1)

    config.set("template", "version", snapshot)

    cmd = "chroot", ROOTFS, "/usr/local/bin/butterknife-prerelease"

    print("Executing:", " ".join(cmd))

    subprocess.call(cmd)

    with open(os.path.join(ROOTFS, "etc/butterknife/butterknife.conf"), "w") as fh:
        config.write(fh)

    cmd = "btrfs", "subvolume", "snapshot", "-r", ROOTFS, \
        "/var/butterknife/pool/@template:%(namespace)s.%(name)s:%(architecture)s:%(version)s" % config["template"]

    print("Executing:", " ".join(cmd))
    subprocess.call(cmd)
        
@click.command("list", help="systemd namespaces that have been prepared for Butterknife")
def nspawn_list():
    for name in os.listdir("/var/lib/machines"):
        rootfs = os.path.join("/var/lib/machines", name)
        
        template_config = os.path.join(rootfs, "etc/butterknife/butterknife.conf")
        if not os.path.exists(template_config):
            print("no config file", template_config)
            continue
        
        config = configparser.ConfigParser()
        config.read('/etc/butterknife/butterknife.conf')
        config.read(template_config)
        if "template" not in config.sections():
            config.add_section("template")
        if "name" not in config["template"]:
            config.set("template", "name", "?")
        
        arch = subprocess.check_output(("file", os.path.join(rootfs, 'bin/bash'))).decode()
        if "32-bit" in arch:
            arch = "x86"
        else:
            arch = "x86_64"
            
        click.echo("%s --> @template:%s:%s:%s" % (name.ljust(20), 
                                                config.get("global", "namespace"),
                                                config.get("template", "name"),
                                                arch))
        
    
@click.command(help="Instantiate template (DANGEROUS!)")
def deploy():
    raise NotImplementedError()
    
@click.group(help="Linux Containers interface")
def lxc(): pass

@click.group(help="systemd-nspawn interface")
def nspawn(): pass

@click.group(help="Receive or serve over multicast")
def multicast(): pass

multicast.add_command(multicast_receive)
multicast.add_command(multicast_send)
lxc.add_command(lxc_release)
lxc.add_command(lxc_list)
nspawn.add_command(nspawn_release)
nspawn.add_command(nspawn_list)

@click.group()
def entry_point(): pass

entry_point.add_command(serve)
entry_point.add_command(pool_clean)
entry_point.add_command(pull)
entry_point.add_command(push)
entry_point.add_command(list)
entry_point.add_command(multicast)
entry_point.add_command(lxc)
entry_point.add_command(nspawn)
entry_point.add_command(deploy)

