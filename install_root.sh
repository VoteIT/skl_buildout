#!/bin/bash
#Ment to be run as root after buildout is done. Will obtain cert and install on nginx debian

cd /etc/nginx
ln -s /home/voteit/srv/skl_buildout/etc/nginx.conf ./sites-available/skl.conf
ln -s ./sites-available/skl.conf ./sites-enabled/.

service nginx stop
certbot certonly --standalone -d skl.voteit.se
service nginx start
