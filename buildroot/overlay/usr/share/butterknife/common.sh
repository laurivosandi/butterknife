#!/bin/bash


function butterknife_partition_size() {
    partition_slug=$(echo $1 | cut -d "/" -f 3)
    sys_part="/sys/block/*/$partition_slug"
    sys_disk=$(dirname $sys_part)
    sector_count=$(cat $sys_part/size)
    sector_size=$(cat $sys_disk/queue/hw_sector_size)
    size=$(expr $sector_count / 1000000 \* $sector_size / 1000)G
    if [ $size == "G" ]; then
        size=$(expr $sector_count / 1000 \* $sector_size / 1000)M
    fi
    echo $size
}

function butterknife_select_disk() {
    for disk in /dev/sd?; do
        disk_slug=$(echo $disk | cut -d "/" -f 3)
        sys_disk="/sys/block/$disk_slug"

        if [ -d $sys_disk/device ]; then
            sector_count=$(cat $sys_disk/size)
            sector_size=$(cat $sys_disk/queue/hw_sector_size)
            # Hack around these dumbass cardreaders
            if [ "$sector_count" == "0" ]; then
                continue
            fi
            size=$(expr $sector_count / 1000000 \* $sector_size / 1000)G
            echo "$disk \"$(cat $sys_disk/device/model | xargs) ($size)\"";
        fi
    done > /tmp/btrfs_volumes
    dialog --menu "Target disk" 0 0 0 \
        --file /tmp/btrfs_volumes
}


function butterknife_select_pool() {
    unset partition
    for uuid in $(blkid -t TYPE=btrfs -o value -s UUID); do
        mountpoint=$(mktemp -d)
        mount UUID=$uuid $mountpoint -o subvol=/
        if [ -d $mountpoint/templates ]; then
            partition=$(blkid -t UUID=$uuid | cut -d ":" -f 1)
            echo "$partition \"$(butterknife_partition_size $partition)\"";
        fi
        umount $mountpoint
        rmdir $mountpoint
    done > /tmp/butterknife_pools

    if [ -z $partition ]; then
        dialog --msgbox "Unable to detect any Butterknife pools" 0 0 
        return 1
    else
        dialog \
            --menu "Select Butterknife pool" 0 0 0 \
            --file /tmp/butterknife_pools
    fi
}
