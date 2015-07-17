Butterknife template helpers
============================

Introduction
------------

The files under overlay/ are intended to be added to a LXC container
that you're using as template for deployment.
We've put significant effort into making the post-deploy and pre-release scripts
usable for as many as possible scenarios, but improvements are very much welcome.
Currently Ubuntu 14.04 i386 and amd64 based templates with legacy GRUB are supported. 

Template guidelines
-------------------

You can make most out of Butterknife if you manage to unify the software and
the configuration of the machines:

* Use centralized login from Samba4, AD, OpenLDAP etc
* Use Puppet, Salt or other configuration management tool to set up template
  and to customize deployed machines.
 
Other nice things:

* Even if a particular software package is required by few users,
  install it in the template.
* Include `NetworkManager configuration <http://lauri.vosandi.com/cfgmgmt/network-manager-system-connections.html>`_ in template
* Use Dconf to customize defaults and lock down attributes of MATE, XFCE, GNOME, etc desktops
* Reduce amount of available locales
* Instead of /etc/skel use /etc/dconf/db/blah.d/, /etc/firefox, /etc/thunderbird
* Most importantly de-duplicate work!

If you're planning to install full-blown desktop you should really pick
one of the following:

.. code:: bash

    sudo apt-get install ubuntu-desktop        # Unity shell
    sudo apt-get install lubuntu-desktop       # LXDE
    sudo apt-get install kubuntu-desktop       # KDE
    sudo apt-get install xubuntu-desktop       # XFCE
    sudo apt-get install ubuntu-mate-desktop   # MATE

This of course contains a lot of useless stuff if you're planning to manage the
image by yourself eg apport, update-notifier etc.

Make sure you have btrfs-tools:

.. code:: bash

    apt-get install btrfs-tools

Make sure you have installed legacy GRUB:

.. code:: bash

    apt-get install grub-pc

Make sure you also have up to date kernel installed, in case of 64-bit Ubuntu 14.04 or
Debian 8 *jessie*:

.. code:: bash

    wget -c http://kernel.ubuntu.com/~kernel-ppa/mainline/v3.18.14-vivid/linux-headers-3.18.14-031814-generic_3.18.14-031814.201505210236_amd64.deb
    wget -c http://kernel.ubuntu.com/~kernel-ppa/mainline/v3.18.14-vivid/linux-headers-3.18.14-031814_3.18.14-031814.201505210236_all.deb
    wget -c http://kernel.ubuntu.com/~kernel-ppa/mainline/v3.18.14-vivid/linux-image-3.18.14-031814-generic_3.18.14-031814.201505210236_amd64.deb
    sudo dpkg -i \
        linux-headers-3.18.14-031814-generic_3.18.14-031814.201505210236_amd64.deb \
        linux-headers-3.18.14-031814_3.18.14-031814.201505210236_all.deb \
        linux-image-3.18.14-031814-generic_3.18.14-031814.201505210236_amd64.deb


Default language can be set via /etc/default/locale.
There are countless aspects when it comes to system customization
which are out of the scope of Butterknife.
