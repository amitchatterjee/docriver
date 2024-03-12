#!/usr/bin/env bash

name=docriver
if [ ! -z "$1" ]; then
    name=$1
fi
echo "Creating keys and certs for $name"
mkdir -p $HOME/.ssh
openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:2048 -keyout $HOME/.ssh/$name.key -out $HOME/.ssh/$name.crt \
    -subj "/C=US/ST=NC/L=RDU/O=Docriver/OU=Dev/CN=$name"
openssl pkcs12 -export -name "$name" \
    -out $HOME/.ssh/$name.p12 -inkey $HOME/.ssh/$name.key -in $HOME/.ssh/$name.crt

ls -al $HOME/.ssh/$name.*


