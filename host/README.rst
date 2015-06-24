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

List local templates at /var/butterknife/pool:

.. code:: bash

    butterknife list

List local templates in a particular directory:

.. code:: bash

    butterknife list file:///path/to/directory
    
List templates at /var/butterknife/pool on a remote machine via SSH:

.. code:: bash

    butterknife list ssh://hostname
    
List templates at remote machine via HTTP:

    butterknife list http[s]://hostname[:port]


Pushing/pulling templates
-------------------------

Currently pull over SSH is working. Following replicates
/var/butterknife/pool from machine *hostname* to local pool
at /var/butterknife/pool:

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

Receiving to local pool at /var/butterknife/pool:

.. code:: bash

    butterknife multicast receive

