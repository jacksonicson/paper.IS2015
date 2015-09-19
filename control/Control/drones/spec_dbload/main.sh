#!/bin/bash

if [ ! -d "/mnt/share" ]; then
	mkdir /mnt/share
fi

# Umount before mounting
umount /mnt/share

# Mount NFS share with dumpfile
mount -t nfs monitor0:/mnt/arr0/share /mnt/share

# Load dumpfile
# mysql -uroot -proot specj < /mnt/share/dumps/specdb\ txrate\ 60.sql

# Copy complete database (much faster then loading the dump file)
systemctl stop mysqld.service
sleep 1

cd /var/lib/mysql
rm -rf *
tar -xzf /mnt/share/mysql.tar.gz
systemctl start mysqld.service

# Umount NFS share
cd /
umount /mnt/share

# Print done
sleep 10

