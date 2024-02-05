#!/usr/bin/env bash

realm=p123456
mime_type="text/plain"
tx_id=$(date +%s)
doc_id=$(uuidgen -t)
doc_version=$(date +%s)
input_file=
doc_type='medical-record'
resource_type='claim'
resource_id='123456789'
resource_description='blah blah blah'
operation=i
command=submit
realm=p123456
file_volume=
server_url=http://localhost:5000/rest/document

OPTIONS="hm:t:d:v:f:y:r:i:p:b:u:"
OPTIONS_DESCRIPTION=$(cat << EOF
<Option(s)>....
    -h: prints this help message
    -m <MIME_TYPE>: mime type. Default: $mime_type
    -t <TX_ID>: transaction id. Default (generated from timestamp): $tx_id
    -d <DOC_ID>: document id. Default (generated from uuid): $doc_id
    -v <VERSION>: document version number. Default (generated from timestap): $doc_version
    -f <FILE_PATH>: input file - Mandatory
    -y <DOC_TYPE>: document type. Default: $doc_type
    -r <REF_RESOURCE_TYPE>: reference resource type. Default: $resource_type
    -i <REF_RESOURCE_ID>: reference resource id. Default: $resource_id
    -p <REF_RESOURCE_DESCRIPTION>: reference resource description. Default: $resource_description
    -b <FILE_VOLUME_BASE>: copy document to file volume and use path as opposed to data in the document/content section of the message. If not specified, inline data is assumed
    -u <SERVER_URL>: URL of the document server REST service. Default: $server_url
EOF
)

while getopts $OPTIONS opt; do
  case "${opt}" in
    m)
      mime_type="$OPTARG"
      ;;
    t)
      tx_id="$OPTARG"
      ;;
    d)
      doc_id="$OPTARG"
      ;;
    v)
      doc_version="$OPTARG"
      ;;
    f)
      input_file="$OPTARG"
      ;;
    y)
      doc_type="$OPTARG"
      ;;
    r)
      resource_type="$OPTARG"
      ;;
    i)
      resource_id="$OPTARG"
      ;;
    p)
      resource_description="$OPTARG"
      ;;
    b)
      file_volume="$OPTARG"
      ;;
    u)
      server_url="$OPTARG"
      ;;
    ?|h)
      echo "Usage: $(basename $0) $OPTIONS_DESCRIPTION"
      exit 0
      ;;
  esac
done
shift "$(($OPTIND -1))"

if [ -z "$input_file" ]; then
    echo "Input file must be specified"
    exit 1
fi

file_content=
mime_content=
if [ -z "$file_volume" ]; then
  raw=$(cat $input_file  | base64 -w 0)
  file_content=$(cat << EOF
"encoding": "base64",
"inline": "$raw"
EOF
)
  mime_content="\"mimeType\": \"${mime_type}\","
else
  # Copy the file to the storage area
  mkdir -p "${file_volume}/${realm}/"
  cp "$input_file" "${file_volume}/${realm}/"
  file_content=$(cat << EOF
"path": "$(basename $input_file)"
EOF
)
fi

cat << EOF > /tmp/docriver-rest.json
{
    "txId": "${tx_id}",
    "realm": "${realm}",
    "documents": [
        {
            "operation": "I",
            "documentId": "${doc_id}",
            "version": ${doc_version},
            "type": "${doc_type}",

            "tags": {
              "tag1": "value1"
            },
            "properties": {
                "key1": "value1"
            },

            "content": {
                $mime_content
                $file_content
            }
        }
    ],
    "references": [
        {
            "resourceType": "${resource_type}",
            "resourceId": "${resource_id}",
            "description": "${resource_description}",
            "properties": {
                "key1": "value1"
            }
        }
    ]
}
EOF

curl -X POST -H 'Content-Type: application/json' -H 'Accept: application/json' --data "@/tmp/docriver-rest.json" "$server_url"
echo

# curl -v -F key1=value1 -F upload=@localfilename URL
# curl -H "Content-Type: multipart/mixed" -F "request={"param1": "value1"};type=application/json" -F "file1=@2.xml" -F "file2=@2.pdf"
