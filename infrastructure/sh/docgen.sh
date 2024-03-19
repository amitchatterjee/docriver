#!/usr/bin/env bash

files=$(ls -1 $DOCRIVER_GW_HOME/infrastructure/doc/*.dot)

target=$DOCRIVER_GW_HOME/target/doc
rm -rf $target
mkdir -p $target

for file in $files; do
    dot -Tsvg $file > $target/$(basename $file).svg
done