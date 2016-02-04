#!/usr/bin/python

# Use this script to migrate
# from /var/butterknife/@template:*:*:snap99 scheme to
# new  /var/lib/butterknife/@template:*:*:timestamp

import os
import subprocess
from datetime import datetime

counter = 0
for subvol in os.listdir("/var/butterknife/pool"):
    if not subvol.startswith("@template:"): continue
    
    timestamp = datetime.fromtimestamp(os.stat("/var/butterknife/pool/" + subvol).st_mtime)
    source = "/var/butterknife/work/" + subvol
    
    if not os.path.exists(source):
        cmd = "/usr/bin/btrfs", "subvol", "snapshot", source, "/var/butterknife/work/" + subvol
        subprocess.call(cmd)
    
    new_scheme = "/var/lib/butterknife/pool/" + subvol.rsplit(":", 1)[0] + ":" + timestamp.strftime("%Y%m%d%H%M%S")
    
    counter += 1
    if os.path.exists(new_scheme):
        print "Already migrated:", timestamp.strftime("%Y%m%d%H%M%S"), subvol
        continue
    
    print "Going to create:", new_scheme
    cmd = "/usr/bin/btrfs", "subvol", "snapshot", "-r", "/var/butterknife/work/" + subvol, new_scheme
    subprocess.call(cmd)    
print "Migrated", counter, "subvolumes"


