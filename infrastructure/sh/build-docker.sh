#!/usr/bin/env  bash

image_name="$1"
if [ -z "$image_name" ]; then
    echo "image name parameter is missing"
    exit 1
fi

version=0.0.1-SNAPSHOT
if [ ! -z "$2" ]; then
    version=$2
fi

target=$DOCRIVER_GW_HOME/target/docker

rm -rf $target
mkdir -p $target

cp -R $DOCRIVER_GW_HOME/docker/$image_name/* $target

docker build -t $image_name:$version $target