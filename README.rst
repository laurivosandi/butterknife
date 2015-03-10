Butterknife provisioning suite
==============================

Butterknife makes Linux deployment dead-simple using the Btrfs filesystem
and LXC containers.

Installation
------------

First set up machine with Ubuntu 14.04 LTS on top of btrfs filesystem to 
be used as snapshot server.

Before doing any filesystem magic ensure that you're running 3.16+ kernel.
You can install Ubuntu 14.10 kernel on 14.04 simply by doing following:

.. code:: bash

    apt-get install linux-image-generic-lts-utopic

Publishing workflow
-------------------

Create LXC container to be used as template for deployment, for instance to 
set up Ubuntu 14.04 container use:

.. code:: bash

    lxc-create -n your-template -B btrfs -t ubuntu -- -r trusty -a amd64

Use your favourite configuration management tool to customize the container,
eg for Puppet users:

.. code:: bash

    puppet apply /etc/puppet/manifests/site.pp

Or just install and tweak whatever you need manually.
To get a working Ubuntu 14.04 desktop install the corresponding metapackage,
this of course contains a lot of useless stuff if you're planning to manage the
image by yourself eg apport, update-notifier etc.

.. code:: bash

    lxc-attach -n your-template
    apt-get update
    apt-get install ubuntu-desktop

Copy post-deploy, pre-release scripts and other helpers:

.. code:: bash

    rsync -av \
        path/to/butterknife/template/overlay/ \
        /var/lib/lxc/your-template/rootfs/

Use butterknife to take a snapshot of the LXC container:

.. code:: bash

    butterknife-release -n your-template
    
Deployment workflow
-------------------

Butterknife provisioning image provides menu-driven user-interface
with simple Enter-Enter-Enter usage:

.. figure:: http://lauri.vosandi.com/cache/85820b490471410cfb1833f074c5ae84.png

    The main menu has convenience entries for shell, reboot and shutdown.
    
.. figure:: http://lauri.vosandi.com/cache/c8683a45f56cc88895646b7090b021af.png

    Target disk selection lists /dev/sd[a-z] entries.
    
.. figure:: http://lauri.vosandi.com/cache/c348448d183ea384b30bbdd4e590cab4.png

    Partition selection.
