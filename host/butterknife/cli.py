
import click
import configparser
import json
import os
import signal
import socket
import subprocess
import http.client
import urllib.request
from butterknife.pool import LocalPool
from butterknife.subvol import Subvol, determine_rootfs_subvol
from butterknife.verify import verify_manifest
from datetime import datetime
from urllib.parse import urlparse

FQDN = socket.getaddrinfo(socket.gethostname(), 0, flags=socket.AI_CANONNAME)[0][3]
BUTTERKNIFE_NAMESPACE = ".".join(reversed(FQDN.split(".")))
BUTTERKNIFE_CONF = "/etc/butterknife/butterknife.conf"
BUTTERKNIFE_CONF_DIR = os.path.dirname(BUTTERKNIFE_CONF)
BUTTERKNIFE_SECRING = os.path.join(BUTTERKNIFE_CONF_DIR, "secring.gpg")
BUTTERKNIFE_PUBRING = os.path.join(BUTTERKNIFE_CONF_DIR, "pubring.gpg")
BUTTERKNIFE_TRUSTED_DIR = os.path.join(BUTTERKNIFE_CONF_DIR, "trusted.gpg.d")
os.environ["GNUPGHOME"] = BUTTERKNIFE_CONF_DIR

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
        keyring = os.path.join(BUTTERKNIFE_TRUSTED_DIR, namespace.replace(".", "_") + ".gpg")
        domain = ".".join(reversed(namespace.split(".")))

        # Check if /etc/butterknife/trusted.gpg.d/<domain>.gpg keyring exists
        # If it does not fetch it from https://<domain>/keyring.gpg

        if not os.path.exists(keyring):
            url = "https://%s/keyring.gpg" % domain
            print("Caching keyring", keyring, "from", url)
            conn = http.client.HTTPSConnection(domain)
            conn.request("GET", "/keyring.gpg")
            response = conn.getresponse()
            body = response.read()

            if response.status == 200:
                fh = open(keyring, "wb")
                fh.write(body)
                fh.close()
            else:
                raise Exception("Failed to fetch keyring %s, server returned %d %s. Please fetch the corresponding GPG key and place to to %s" % (url, response.status, body.decode("ascii"), keyring))

            # TODO: Fall back to plain HTTP if HTTPS is not configured (?)
            # TODO: Check for sane directory permissions

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
                pv = subprocess.Popen(("pv",), stdin=btrfs_send.stdout, stdout=subprocess.PIPE)
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
    def __init__(self, pattern="@template:*.*:*:*", signed=False):
        self.category, name, self.architecture, self.version = pattern.split(":")
        self.namespace, self.identifier = name.rsplit(".", 1)
        self.signed = signed

    def match(self, subvol):
        if self.signed and not subvol.signed: # Subvolume is not signed, but signature is required
            return False
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
                
    def subset(self, namespace="*", identifier="*", architecture="*", version="*", signed=False):
        return Filter(
            "%s:%s.%s:%s:%s" % (
                self.category,
                self.namespace if namespace == "*" else namespace,
                self.identifier if identifier == "*" else identifier,
                self.architecture if architecture == "*" else architecture,
                self.version if version == "*" else version),
                True if signed else self.signed)


@click.command("serve", help="Run built-in HTTP server")
@click.argument("subvol", default="@template:*.*:*:*")
@click.option("-u", "--user", default=None, help="Run as user")
@click.option("-p", "--port", default=80, help="Listen port")
@click.option("-l", "--listen", default="0.0.0.0", help="Listen address")
def serve(subvol, user, port, listen):
    signal.signal(signal.SIGCHLD, signal.SIG_IGN) # Prevent btrfs [defunct]

    subvol_filter = Filter(subvol)
    pool = LocalPool()
    click.echo("Serving %s from %s at %s:%d" % (subvol, pool, listen, port))
    from butterknife.api import TemplateResource, VersionResource, \
        LegacyStreamingResource, SubvolResource, StreamResource, \
        ManifestResource, SignatureResource, KeyringResource, PackageDiff
    import pwd
    import falcon
    from wsgiref.simple_server import make_server, WSGIServer
    from socketserver import ThreadingMixIn

    class DenyCrawlers(object):
        def on_get(self, req, resp):
            resp.body = "User-agent: *\nDisallow: /\n"

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
    app.add_route("/@{subvol}/manifest/", ManifestResource(pool, subvol_filter))
    app.add_route("/@{subvol}/signature/", SignatureResource(pool, subvol_filter))
    app.add_route("/@{subvol}/packages/", PackageDiff(pool, subvol_filter))
    app.add_route("/keyring.gpg", KeyringResource(BUTTERKNIFE_PUBRING))
    app.add_route("/robots.txt", DenyCrawlers())

    httpd = make_server(listen, port, app, ThreadingWSGIServer)
    if user:
        _, _, uid, gid, gecos, root, shell = pwd.getpwnam(user)
        sudoer = os.path.join("/etc/sudoers.d", user)

        if uid == 0:
            print("Please specify unprivileged user, eg 'butterknife'")
            exit(254)
        elif not os.path.exists(sudoer):
            print("Please create %s with following content: %s ALL=(ALL) NOPASSWD: /usr/bin/btrfs send /var/lib/butterknife/pool/@template\\:*" % (sudoer, user))
            exit(253)

        print("Switching to user %s (uid=%d, gid=%d)" % (user, uid, gid))
        os.setgid(gid)
        os.setuid(uid)
    elif os.getuid() == 0:
        click.echo("Warning: running as root, this is not reccommended!")

    try:
        import dbus
    except ImportError:
        print("Could not import dbus, gobject or avahi - Avahi advertisement of service disabled")
        group = None
    else:
        service_name = "Butterknife server at " + socket.gethostname() + (" port %d" % port if port != 80 else "")
        bus = dbus.SystemBus()
        try:
            server = dbus.Interface(
                bus.get_object("org.freedesktop.Avahi", "/"),
                "org.freedesktop.Avahi.Server")
        except dbus.exceptions.DBusException:
            click.echo("Avahi not running, skipping advertisement")
        else:
            click.echo("Advertising via Avahi: %s" % service_name)
            group = dbus.Interface(
                bus.get_object('org.freedesktop.Avahi', server.EntryGroupNew()),
                "org.freedesktop.Avahi.EntryGroup")
            group.AddService(
                -1,
                -1,
                dbus.UInt32(0),
                service_name.encode("ascii"),
                b"_butterknife._tcp",
                b"local",
                (socket.gethostname() + ".local").encode("ascii"),
                dbus.UInt16(port), [b"path=/"])
            group.Commit()

    httpd.serve_forever()

    if not group is None:
        group.Free()

@click.command("receive", help="Receive subvolume over multicast")
@click.option("--pool", default="file:///var/lib/butterknife/pool", help="Remote or local pool")
def multicast_receive(pool):
    cmd = "udp-receiver", "--nokbd"
    udpcast = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    pool = pool_factory(pool)
    pool.receive(udpcast.stdout)
    udpcast.wait()

@click.command("send", help="Send subvolume over multicast")
@click.argument("subvol")
@click.option("--pool", default="file:///var/lib/butterknife/pool", help="Remote or local pool")
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
    config.read(BUTTERKNIFE_CONF)

    import lxc
    container=lxc.Container(name)
    was_running = container.running

    if was_running:
        print("Stopping container")
        container.stop()


    ROOTFS = container.get_config_item("lxc.rootfs")
    assert os.path.isdir(ROOTFS), "No directory at %s" % ROOTFS

    DEPLOY_SCRIPTS = os.path.join(ROOTFS, "etc", "butterknife", "deploy.d")
    assert os.path.isdir(DEPLOY_SCRIPTS), "Postinstall scripts directory %s missing!" % DEPLOY_SCRIPTS

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

    config.set("template", "version", datetime.now().strftime("%Y%m%d%H%M%S"))

    print("Created snapshot:", snapshot)

    snapdir = os.path.join("/var/lib/lxcsnaps", name, snapshot)

    cmd = "chroot", os.path.join(snapdir, "rootfs"), "/usr/local/bin/butterknife-prepare"

    print("Executing:", " ".join(cmd))

    import subprocess
    subprocess.call(cmd)

    with open(os.path.join(snapdir, "rootfs", BUTTERKNIFE_CONF[1:]), "w") as fh:
        config.write(fh)

    cmd = "btrfs", "subvolume", "snapshot", "-r", os.path.join(snapdir, "rootfs"), \
        "/var/lib/butterknife/pool/@template:%(namespace)s.%(name)s:%(architecture)s:%(version)s" % config["template"]

    print("Executing:", " ".join(cmd))
    subprocess.call(cmd)

    if was_running:
        print("Restarting container")
        container.start()

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
        config.read(BUTTERKNIFE_CONF)
        config.read(template_config)
        if "template" not in config.sections():
            config.add_section("template")
        if "name" not in config["template"]:
            config.set("template", "name", "?")
        click.echo("%s --> @template:%s:%s:%s" % (name.ljust(40), config.get("global", "namespace"), config.get("template", "name"), container.get_config_item("lxc.arch")))

@click.command("clean", help="Clean incomplete transfers")
def pool_clean():
    for path in os.listdir("/var/lib/butterknife/pool"):
        if not path.startswith("@template:"):
            continue
        try:
            open(os.path.join("/var/lib/butterknife/pool", path, ".test"), "w")
        except OSError as e:
            if e.errno == 30: # This is read-only, hence finished
                continue
        cmd = "btrfs", "subvol", "delete", os.path.join("/var/lib/butterknife/pool", path)
        click.echo("Executing: %s" % " ".join(cmd))
        subprocess.check_output(cmd)

@click.command("release", help="Release systemd namespace as Butterknife template")
@click.argument("name")
def nspawn_release(name):
    config = configparser.ConfigParser()
    config.read(BUTTERKNIFE_CONF)
    
    click.echo("Make sure that your nspawn container isn't running!")

    ROOTFS = os.path.join("/var/lib/machines", name)
    assert os.path.isdir(ROOTFS), "No directory at %s" % ROOTFS

    DEPLOY_SCRIPTS = os.path.join(ROOTFS, "etc", "butterknife", "deploy.d")
    assert os.path.isdir(DEPLOY_SCRIPTS), "Postinstall scripts directory %s missing!" % DEPLOY_SCRIPTS

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

    cmd = "chroot", ROOTFS, "/usr/local/bin/butterknife-prepare"

    print("Executing:", " ".join(cmd))

    subprocess.call(cmd)

    with open(os.path.join(ROOTFS, "etc/butterknife/butterknife.conf"), "w") as fh:
        config.write(fh)

    cmd = "btrfs", "subvolume", "snapshot", "-r", ROOTFS, \
        "/var/lib/butterknife/pool/@template:%(namespace)s.%(name)s:%(architecture)s:%(version)s" % config["template"]

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
        config.read(BUTTERKNIFE_CONF)
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

@click.command(help="Initialize Butterknife host")
@click.option("-e", "--endpoint", default="https://" + FQDN, help="Butterknife endpoint URL")
@click.option("-n", "--namespace", default=BUTTERKNIFE_NAMESPACE, help="Butterknife namespace")
def init(endpoint, namespace):

    if not os.path.exists(BUTTERKNIFE_CONF):
        if not os.path.exists(BUTTERKNIFE_CONF_DIR):
            os.makedirs(BUTTERKNIFE_CONF_DIR)
        else:
            print("Configuration directory", BUTTERKNIFE_CONF_DIR, "exists.")

        config = configparser.ConfigParser()
        config.add_section("global")
        config.set("global", "namespace", namespace)
        config.set("global", "endpoint", endpoint)

        config.add_section("signing")
        config.set("signing", "namespace", namespace)

        with open(BUTTERKNIFE_CONF, 'w') as fh:
            config.write(fh)

        print("Generated %s" % BUTTERKNIFE_CONF)
    else:
        print("Configuration already exists in", BUTTERKNIFE_CONF)

    if not os.path.exists(os.path.join(BUTTERKNIFE_CONF_DIR, "trustdb.gpg")):
        print("Follow next steps to set up GPG in", BUTTERKNIFE_CONF_DIR, "for snapshot signatures.")
        os.system("gpg --gen-key")
    else:
        print("GPG already set up")

    if not os.path.exists(BUTTERKNIFE_TRUSTED_DIR):
        os.makedirs(BUTTERKNIFE_TRUSTED_DIR)
    else:
        print("Trusted keyrings directory", BUTTERKNIFE_TRUSTED_DIR, "exists.")


@click.command(help="Sign manifest")
@click.argument("manifest")
def sign(manifest):
    config = configparser.ConfigParser()
    config.read(BUTTERKNIFE_CONF)
    signing_namespace = config.get("signing", "namespace")
    keyring = os.path.join(os.path.dirname(BUTTERKNIFE_CONF), "secring.gpg")
    if not os.path.exists(keyring):
        print("Private keyring", keyring, "not available")
        
    subprocess.call(("gpg", "--armor", "--detach-sign", manifest))


@click.command(help="Verify")
@click.option("-s", "--subvol", default=determine_rootfs_subvol(), help="Subvolume to be checked, template of currently running rootfs by default")
@click.option("-m", "--manifest", help="Manifest to be used for checking")
def verify(subvol, manifest):
    if os.getuid():
        raise click.ClickException("Run as root or use sudo")
    if not manifest:
        manifest = "/var/lib/butterknife/manifests/%s" % subvol

    if not subvol:
        raise click.ClickException("Failed to determine template corresponding to root filesystem, try specifying particular template to verify")

    click.echo("Verifying %s" % subvol)

    if subvol.endswith("/"):
        subvol = subvol[:-1]
    if not subvol.startswith("/"):
        subvol = os.path.join("/var/lib/butterknife/pool", subvol)

    verify_manifest(subvol) # This will raise exceptions
    click.echo("Verification successful")

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

entry_point.add_command(init)
entry_point.add_command(sign)
entry_point.add_command(verify)
entry_point.add_command(serve)
entry_point.add_command(pool_clean)
entry_point.add_command(pull)
entry_point.add_command(push)
entry_point.add_command(list)
entry_point.add_command(multicast)
entry_point.add_command(lxc)
entry_point.add_command(nspawn)
entry_point.add_command(deploy)

