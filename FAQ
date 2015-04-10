Frequently asked questions
--------------------------

Q: Is it like cloning?
A: Not exactly, requires taking machines offline
   for cloning process and you can not perform
   incremental updates.
   Even now we support *receive* functionality
   which pulls changed files from the server.
   By the end of summer of 2015 we're planning to
   have online incremental updates, which means
   that the machine can download and apply 
   new snapshot while the machine is up, running and
   in use.

Q: Can I run the infrastructure on my own?
A: Absolutely, that was the plan - to
   provide tools to set up template machine,
   template versioning and deployment on bare metal.
   We've put extra effort into the naming scheme
   so you can mix templates from different servers,
   run a downstream server with your templates etc.
   
Q: Isn't Btrfs unstable?
A: Btrfs support in Linux 3.16 has proven to be pretty
   reliable. We haven't faced any issues like 
   we did with 3.14 and earlier kernels.

Q: Why not use CoreOS, Ubuntu Core, Docker, etc?
A: Most systems which provide atomic root filesystem updates
   are designed for headless servers and don't even
   have video drivers bundled with the operating system and
   even if they did it would be very tricky to use
   video hardware from within the containers.
   Butterknife attempts to provide atomic updates
   for workstations and at the same time remain compatible
   with already existing operating systems such as Ubuntu,
   Fedora, Red Hat etc.

