#!/bin/bash
set -e

# Génère le keyfile si il n'existe pas déjà
if [ ! -f /etc/mongo-keyfile/mongo-keyfile ]; then
  mkdir -p /etc/mongo-keyfile
  openssl rand -base64 756 > /etc/mongo-keyfile/mongo-keyfile
  chmod 400 /etc/mongo-keyfile/mongo-keyfile
fi

# Démarre MongoDB
exec mongod --replSet rs0 --keyFile /etc/mongo-keyfile/mongo-keyfile --bind_ip_all --auth