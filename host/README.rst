Butterknife command-line utility
================================

Introduction
------------

Butterknife command-line utility can be used to serve snapshots via HTTP;
send and receive snapshots over SSH and multicast;
list local and remote snapshots.

Installation
------------

Install dependencies:

.. code:: bash

    sudo apt-get install lxc python3-dev cython3 python3-pip pigz btrfs-progs
    sudo apt-get install python3-lxc # Ubuntu 14.04 or older
    sudo pip3 install jinja2 click falcon

Install Butterknife:

.. code:: bash

    sudo pip3 install butterknife


Listing templates
-----------------

List local templates at /var/lib/butterknife/pool:

.. code:: bash

    butterknife list

List local templates in a particular directory:

.. code:: bash

    butterknife list file:///path/to/directory
    
List templates at /var/lib/butterknife/pool on a remote machine via SSH:

.. code:: bash

    butterknife list ssh://hostname
    
List templates at remote machine via HTTP:

.. code:: bash

    butterknife list http[s]://hostname[:port]


Pushing/pulling templates
-------------------------

Currently pull over SSH is working. Following replicates
/var/lib/butterknife/pool from machine *hostname* to local pool
at /var/lib/butterknife/pool:

.. code:: bash

    butterknife pull ssh://hostname

You can also pull via HTTP:

.. code:: bash

    butterknife pull http://butterknife.koodur.com
    
Note that symmetric push/pull requires patched btrfs-progs which has additional -p and -C flags for btrfs receive.


Multicast
---------

Sending local template via multicast:

.. code:: bash

    butterknife multicast send @template\:com.koodur.butterknife.Ubuntu\:x86_64\:snap7

You can even multicast a remote subvolume:

.. code:: bash

    butterknife multicast send @template\:com.koodur.butterknife.Ubuntu\:x86_64\:snap7 --pool ssh://hostname

Receiving to local pool at /var/lib/butterknife/pool:

.. code:: bash

    butterknife multicast receive

systemd-nspawn workflow
-----------------------

Create a btrfs subvolume for your butterknife image under /var/lib/machines. 
Replace ArchLinux with your image name you want to use.

.. code:: bash

    sudo btrfs subvolume create /var/lib/machines/ArchLinux

Install base system in there

.. code:: bash

    sudo pacstrap -i -c -d /var/lib/machines/ArchLinux base

Nspawn into it and customize your container

.. code:: bash

    sudo systemd-nspawn -M ArchLinux
    # do your thing

You will also need some scripts that will be ran on snapshot creation and when
doing deployments with provision image.

look into the `puppet-butterknife <https://github.com/laurivosandi/puppet-butterknife>`_ repository for scripts and files you should add


Create butterknife config file in
/var/lib/machines/ArchLinux/etc/butterknife/butterknife.conf

.. code:: ini

    [template]
    name=ArchLinux
    
Also make sure that you have something like this on your host 
etc/butterknife/butterknife.conf config file

.. code:: ini

    [global]
    namespace=org.example.butterknife
    endpoint=https://butterknife.example.org

Take a snapshot of your image

.. code:: bash

    butterknife nspawn release ArchLinux

And now you should be ready to serve that image to your clients
