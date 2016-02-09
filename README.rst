Butterknife provisioning suite
==============================

Butterknife is the last missing piece of the puzzle that makes
Linux-based desktop OS deployment a breeze. Butterknife complements your
Puppet or Salt infrastructure and reduces the time you spend
setting up Linux-based desktop machines.

.. figure:: doc/img/butterknife-usecase-tee.png

    Butterknife with off-site server and multicast

For demo and details check out project homepage at `butterknife.rocks <http://butterknife.rocks/>`_.
Detailed background of the work is described in the
`white paper
<https://owncloud.koodur.com/index.php/s/5KOgVze9X2cOUkD>`_.
You can check out production instance of Butterknife server at
`butterknife.koodur.com <https://butterknife.koodur.com/>`_.


Features
--------

We basically mixed Linux Containers with Btrfs filesystem and that resulted in pure awesomeness:

* Based on Btrfs snapshots technology, supports incremental upgrades
* Works with Puppet, Salt or any other configuration management software
* Persistent subvolume for /home, remote management keys and domain membership
* Supports multicast for blasting template on multiple machines simultaneously
* Avahi advertisement over mDNS, no need to configure DNS/DHCP server
* Written mostly in Python, provisioning image built with Buildroot


Installation
------------

Current instructions are based on Debian 8, but any modern Linux-based
OS should suffice.
First set up machine with Debian 8 on top of Btrfs filesystem to
be used as snapshot server.

Before doing any filesystem magic ensure that you're running 4.3.3+ kernel.
You can install up to date kernel on Debian 8 and Ubunut 14.04 simply by doing following:

.. code:: bash

    wget -c \
        http://kernel.ubuntu.com/~kernel-ppa/mainline/v4.4.1-wily/linux-image-4.4.1-040401-generic_4.4.1-040401.201601311534_amd64.deb \
        http://kernel.ubuntu.com/~kernel-ppa/mainline/v4.4.1-wily/linux-headers-4.4.1-040401-generic_4.4.1-040401.201601311534_amd64.deb \
        http://kernel.ubuntu.com/~kernel-ppa/mainline/v4.4.1-wily/linux-headers-4.4.1-040401_4.4.1-040401.201601311534_all.deb
    dpkg -i \
        linux-image-4.4.1-040401-generic_4.4.1-040401.201601311534_amd64.deb \
        linux-headers-4.4.1-040401-generic_4.4.1-040401.201601311534_amd64.deb \
        linux-headers-4.4.1-040401_4.4.1-040401.201601311534_all.deb

On Ubuntu 14.04 you also need to install updated btrfs-tools:

.. code:: bash

    wget -c http://launchpadlibrarian.net/190998686/btrfs-tools_3.17-1.1_amd64.deb
    dpkg -i btrfs-tools_3.17-1.1_amd64.deb

Make sure the LXC container directories are also mounted with *noatime*
and *nodiratime* flag otherwise all the access times reflect in differential
updates as well causing excessive traffic.
Finally install the `Butterknife command-line utility <host/>`_:

.. code:: bash

    pip3 install butterknife


Publishing workflow
-------------------

Create LXC container to be used as template for deployment, for instance to
set up Ubuntu 14.04 based template use:

.. code:: bash

    lxc-create -n your-template -B btrfs -t ubuntu -- -r trusty -a amd64

Customize mountpoints in /var/lib/lxc/your-template/fstab, for example:

.. code::

    /var/cache/apt/archives /var/lib/lxc/your-template/rootfs/var/cache/apt/archives none bind
    /etc/puppet/ /var/lib/lxc/your-template/rootfs/etc/puppet/ none bind,ro

Start and enter the container:

.. code:: bash

    lxc-start -d -n your-template
    lxc-attach -n your-template

Use your favourite configuration management tool to customize the template,
eg for Puppet users:

.. code:: bash

    puppet apply /etc/puppet/manifests/site.pp

Or just install and tweak whatever you need manually.
Futher instructions for customizing the template can be found `here <template/>`_.

Copy post-deploy, pre-release scripts and other helpers:

.. code:: bash

    rsync -av \
        path/to/butterknife/template/overlay/ \
        /var/lib/lxc/your-template/rootfs/

Create Butterknife configuration for the template in
/var/lib/lxc/your-template/rootfs/etc/butterknife/butterknife.conf:

.. code:: ini

    [template]
    name=YourTemplateName

Also create Butterknife configuration for the host in
/etc/butterknife/butterknife.conf:

.. code:: ini

    [global]
    namespace=org.example.butterknife
    endpoint=https://butterknife.example.org

This results template snapshot names with following scheme:

.. code::

    @template:org.example.butterknife.YourTemplateName:x86:20160102030405
    @template:org.example.butterknife.YourTemplateName:x86:20160102030415
    @template:org.example.butterknife.YourTemplateName:x86:20160102030425
    etc ...

Use butterknife to take a snapshot of the LXC container:

.. code:: bash

    butterknife lxc release your-template

Finally fire up the Butterknife server:

.. code:: bash

    butterknife serve


Serving provisioning image over PXE
-----------------------------------

PXE is the preferred way of serving the provisioning image.
In this case Ubuntu/Debian is used to host the provisioning images.

.. code:: bash

    sudo apt-get install syslinux tftpd-hpa memtest86+
    mkdir -p /var/lib/tftpboot/
    cp /boot/memtest86+.bin /var/lib/tftpboot/
    cp /usr/lib/syslinux/pxelinux.0 /var/lib/tftpboot/
    cp /usr/lib/syslinux/*.c32 /var/lib/tftpboot/
    wget http://butterknife.rocks/provision/butterknife-amd64.bin \
        -O /var/lib/tftpboot/butterknife-amd64.bin

In Ubuntu ``tftp-hpa`` listens only on IPv6 addresses, this can be fixed with:

.. code:: bash

    sed -i -e 's/TFTP_ADDRESS=/TFTP_ADDRESS=":69"/' /etc/default/tftpd-hpa

Set up following in /var/lib/tftpboot/pxelinux.cfg/default:

.. code::

    default menu.c32
    prompt 0
    timeout 600
    menu title Butterknife provisioning tool

    label mbr
        menu label Boot from local harddisk
        localboot 0

    label mbr
        menu label Boot from first partition
        kernel chain.c32
        append hd0 1

    label butterknife-amd64
        menu label Butterknife
        linux butterknife-amd64.bin

    label deploy-edu-workstation
        menu label Deploy edu workstation
        linux butterknife-amd64.bin
        append bk_url=https://butterknife.koodur.com bk_template=com.koodur.butterknife.EduWorkstation quiet

    label memtest
        menu label Memtest86+
        linux memtest86+.bin


Setting up PXE boot
-------------------

If you're running ISC DHCP server add following to your subnet section
in /etc/dhcp/dhcpd.conf and restart the service:

.. code::

    next-server 192.168.x.x;
    filename "pxelinux.0";

If you have OpenWrt based router simply add following to
the **config dnsmasq** section of /etc/config/dhcp and restart
the service:

.. code::

    option dhcp_boot 'pxelinux.0,,192.168.x.x'

If running vanilla *dnsmasq*, then simply add following to /etc/dnsmasq.conf
and restart the service:

.. code::

    dhcp-boot=pxelinux.0,,192.168.x.x

If you're using MikroTik's WinBox open up your DHCP network configuration and
set **Next Server** option to 192.168.x.x and **Boot file name** option to
pxelinux.0:

.. figure:: doc/img/mikrotik-pxe-boot.png

Remember to replace 192.168.x.x with the actual IP address of your TFTP server.


Deployment workflow
-------------------

Butterknife provisioning image provides menu-driven user-interface
with simple Enter-Enter-Enter usage:

.. figure:: doc/img/butterknife-main-screen.png

We currently support HTTP, multicast and various combinations of both:

.. figure:: doc/img/butterknife-transfer-method.png

Partitioning choices feature also NTFS resize and incremental upgrades:

.. figure:: doc/img/butterknife-partitioning-method.png

Target disk selection:

.. figure:: http://lauri.vosandi.com/cache/c8683a45f56cc88895646b7090b021af.png

Partition selection:

.. figure:: http://lauri.vosandi.com/cache/c348448d183ea384b30bbdd4e590cab4.png

Template versions are actually snapshots:

.. figure:: doc/img/butterknife-select-version.png

These steps should be enough to deploy a Linux-based OS in no time.
You can follow instructions `here <provision/>`_ to assemble the
provisioning image from scratch.

Recovery console
----------------

In case you need to recover already deployed instance or delete old
templates pick Advanced Options from main menu which brings up following:

.. figure:: doc/img/butterknife-advanced-options.png

All instances can be easily entered via instance maintenance entry:

.. figure:: doc/img/butterknife-instance-list.png


Contact
-------

Feel free to join the `#butterknife channel at Freenode IRC
<https://webchat.freenode.net/?channels=butterknife&nick=butterknife-user>`_ or
to open issue `here at GitHub <http://github.com/laurivosandi/butterknife/issues/>`_.
