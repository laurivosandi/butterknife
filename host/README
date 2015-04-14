Butterknife command-line utility
================================

Install dependencies:

    sudo apt-get install python3-pip python3-lxc pigz btrfs-progs
    sudo pip3 install falcon click

Place overlay/usr/bin/butterknife somewhere in PATH, eg /usr/bin and make it executable.


Listing templates
-----------------

List local templates at /var/butterknife/pool:

.. code:: bash

    butterknife list
    
List templates at /var/butterknife/pool on a remote machine via SSH:

.. code:: bash

    butterknife list --pool ssh://hostname


Pushing/pulling templates
-------------------------

Currently pull over SSH is working. Following replicates
/var/butterknife/pool from machine *hostname* to local pool
at /var/butterknife/pool:

.. code:: bash

    butterknife pull --source ssh://hostname

Of course you can apply filters:

.. code:: bash

    butterknife pull --source ssh://hostname --architecture x86 --namespace com.koodur.butterknife
    

Multicast
---------

Sending local template via multicast:

.. code:: bash

    butterknife multicast --namespace org.example --identifier TemplateName --arch x86 --version snap0

Receiving to local pool at /var/butterknife/pool:

.. code:: bash

    butterknife multicast receive
