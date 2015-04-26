Butterknife command-line utility
================================

Install dependencies:

.. code:: bash

    sudo apt-get install python3-pip python3-lxc pigz btrfs-progs
    sudo pip3 install falcon click

Place overlay/usr/bin/butterknife somewhere in PATH, eg /usr/bin and make it executable.


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

Of course you can apply filters:

.. code:: bash

    butterknife pull ssh://hostname --architecture x86 --namespace com.koodur.butterknife

You can also pull via HTTP:

.. code:: bash

    butterknife pull http[s]://hostname[:port]
    
Note that symmetric push/pull requires patched btrfs-progs which has additional -p and -C flags for btrfs receive.

Multicast
---------

Sending local template via multicast:

.. code:: bash

    butterknife serve multicast @template\:com.koodur.butterknife.Ubuntu\:x86_64\:snap7

You can even multicast a remote subvolume:

.. code:: bash

    butterknife serve multicast @template\:com.koodur.butterknife.Ubuntu\:x86_64\:snap7 --pool ssh://hostname

Receiving to local pool at /var/butterknife/pool:

.. code:: bash

    butterknife multicast receive

