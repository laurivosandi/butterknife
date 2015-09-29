Butterknife provisioning image
==============================

We're using Buildroot to generate all-in-one (<15MB) provisioning image
which can be either booted via PXE or from a USB memory stick.

Steps to reproduce the image:

.. code:: bash

    wget -c http://buildroot.uclibc.org/downloads/buildroot-2015.08.1.tar.bz2
    tar xvjf buildroot-2015.08.1.tar.bz2
    cd buildroot-2015.08.1
    patch -p1 < path/to/butterknife/buildroot/patches/ms-sys.diff

To tweak the build:

.. code:: bash

    make menuconfig

In menuconfig enable following:

.. code::

    System configuration --->
        Init system (None)
        Root filesystem overlay directories (path/to/butterknife/buildroot/overlay)
    Toolchain  --->
        [*] Enable WCHAR support
    Kernel  --->
        [*] Linux Kernel
            Kernel Version (Same as toolchain headers)
            Kernel configuration (Using a custom config file)
            Configuration file path (path/to/butterknife/buildroot/kernel-i386.config)
    Bootloaders  --->
        [*] syslinux
              Image to install (isolinux)
    Filesystem images  --->
        [*] initial RAM filesystem linked into linux kernel
        -*- cpio the root filesystem
              Compression method (xz)
        [*] iso image
              Bootloader (isolinux)
        [*] Build hybrid image
    Target packages  --->
        Shell and utilities  --->
            [*] dialog
        Development tools  --->
            [*] jq
        Networking applications
            [*] bind
            [ ]   Install server components
            [*]   Install tools
            [*] ntp
            [*]   ntpdate
            [*] udpcast
                udpcast tools selection  --->
                    [*] sender
                    [*] receiver
        System tools  --->
            [*] util-linux
            [*] install utilities
        Libraries  --->
            Crypto  --->
                [*] CA Certificates
                [*] openssl
            Networking  --->
                [*] libcurl
                [*]   curl binary
        Filesystem and flash utilities  --->
            [*] ms-sys
            [*] btrfs-progs
            [*] ntfs-3g
            [*]   ntfsprogs
        Hardware handling  --->
            [*] pciutils

Additionally you might want to tweak kernel or busybox:

.. code:: bash

    make linux-menuconfig
    make busybox-menuconfig

Make sure you:

* use fdisk from util-linux, not from busybox.
* enable support for necessary ethernet cards, USB and SATA controllers

To compile the image run:

.. code:: bash

  make

