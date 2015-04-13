Frequently asked questions
==========================

Is it like cloning?
-------------------

Not exactly, cloning requires taking machines offline
for cloning process and you can not perform
incremental updates.
Even now we support *receive* functionality
which pulls changed files from the server.
By the end of summer of 2015 we're planning to
have online incremental updates, which means
that the machine can download and apply 
new snapshot while the machine is up, running and
in use.

Can I run the infrastructure on my own?
---------------------------------------

Absolutely, that was the plan - to
provide tools to set up template machine,
template versioning and deployment on bare metal.
We've put extra effort into the naming scheme
so you can mix templates from different servers,
run a downstream server with your templates etc.
   
Isn't Btrfs unstable?
---------------------

Btrfs support in Linux 3.16 has proven to be pretty
reliable. We haven't faced any issues like 
we did with 3.14 and earlier kernels.

Why not ZFS?
------------

ZFS is great for network attached storage and servers.
To use ZFS at least 1GB of memory is reccommended,
which most often means that you're not running ZFS on a
workstation or laptop. Also ZFS was designed for 64-bit systems,
at the moment ZFS builds for 32-bit Linuces but it's not considered stable [#zfsonlinux]_.
Due to licensing issues it is not possible to merge
the original ZFS driver in Linux upstream,
meaning it's tricky to install any Linux-based OS
on ZFS root filesystem.

.. [#zfsonlinux] http://zfsonlinux.org/faq.html

Why not use CoreOS, Ubuntu Core, Docker, etc?
---------------------------------------------

Most systems which provide atomic root filesystem updates
are designed for headless servers and don't even
have video drivers bundled with the operating system and
even if they did it would be very tricky to use
video hardware from within the containers.
Butterknife attempts to provide atomic updates
for workstations and at the same time remain compatible
with already existing operating systems such as Ubuntu,
Fedora, Red Hat etc.

