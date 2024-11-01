#!/usr/bin/env  bash

tomls=$(find $DOCRIVER_GW_HOME -name '*.toml')
for toml in $tomls; do 
    cd $(dirname $toml)
    echo "------------------------------------------------"
    echo "Buildling wheel for: $(pwd)"
    echo "------------------------------------------------"
    python -m build --wheel
done
