#!/usr/bin/env bash

name=docriver
if [ ! -z "$1" ]; then
    name=$1
fi

folder=$HOME/.ssh
if [ ! -z "$2" ]; then
    folder=$2
fi

echo "Creating keys and certs for $name in folder $folder"
mkdir -p $folder
openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:2048 -keyout $folder/$name.key -out $folder/$name.crt \
    -subj "/C=US/ST=NC/L=RDU/O=Docriver/OU=Dev/CN=$name"
openssl pkcs12 -export -name "$name" \
    -out $folder/$name.p12 -inkey $folder/$name.key -in $folder/$name.crt

ls -al $folder/$name.*


