#!/usr/bin/env  bash

version=0.0.1-SNAPSHOT
if [ ! -z "$1" ]; then
    version=$1
fi

target=$DOCRIVER_GW_HOME/target/docker

rm -rf $target
mkdir -p $target

cp -R $DOCRIVER_GW_HOME/docker/* $target

docker build -t docriver-base:$version $target