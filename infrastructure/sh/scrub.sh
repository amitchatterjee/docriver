#!/usr/bin/env bash

objs=$(mc ls  docriver/docriver --json | jq -r .key)
for obj in $objs; do echo $obj;
    mc rm --recursive --force docriver/docriver/"$obj"
done

echo 'DELETE FROM TX; DELETE FROM DOC;'| mysql -h 127.0.0.1 -u docriver -p${DOCRIVER_MYSQL_PASSWORD} docriver