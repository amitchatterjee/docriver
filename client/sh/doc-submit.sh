#!/usr/bin/env bash

realm=p123456
mime_type="text/plain"
tx_id=$(date +%s)
doc_id=$(uuidgen -t)
input_file=
doc_type='medical-record'
resource_type='claim'
resource_id='123456789'
resource_description='blah blah blah'
command=submit
realm=p123456
file_volume=
server_url=http://localhost:5000/tx
replaces_doc_id=
keystore_file=$HOME/.ssh/docriver/docriver.p12
keystore_password=docriver

OPTIONS="hm:t:d:v:f:y:r:i:p:b:u:l:k:w:"
OPTIONS_DESCRIPTION=$(cat << EOF
<Option(s)>....
    -h: prints this help message
    -m <MIME_TYPE>: mime type. Default: $mime_type
    -t <TX_ID>: transaction id. Default (generated from timestamp): $tx_id
    -d <DOC_ID>: document id. Default (generated from uuid): $doc_id
    -f <FILE_PATH>: input file to send. If not specified, the document specified by the -d option must exist
    -y <DOC_TYPE>: document type. Default: $doc_type
    -r <REF_RESOURCE_TYPE>: reference resource type. Default: $resource_type
    -i <REF_RESOURCE_ID>: reference resource id. Default: $resource_id
    -p <REF_RESOURCE_DESCRIPTION>: reference resource description. Default: $resource_description
    -b <FILE_VOLUME_BASE>: copy document to file volume and use path as opposed to data in the document/content section of the message. If not specified, inline data is assumed
    -u <SERVER_URL>: URL of the document server REST service. Default: $server_url
    -l <REPLACES_DOC_ID> if this document is replacing another document
    -k <AUTH_KEY_FILE> the keystore file that contains the key for signing the JWT auth token
    -w <AUTH_KEY_PASSWORD> the keystore file password
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
    l)
      replaces_doc_id="$OPTARG"
      ;;
    k)
      keystore_file="$OPTARG"
      ;;
    w)
      keystore_password="$OPTARG"
      ;;
    ?|h)
      echo "Usage: $(basename $0) $OPTIONS_DESCRIPTION"
      exit 0
      ;;
  esac
done
shift "$(($OPTIND -1))"

file_content=
mime_content=
replaces_content=
if [ ! -z "$input_file" ]; then
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

  if [ ! -z "$replaces_doc_id" ]; then
    replaces_content="\"replaces\": \"$replaces_doc_id\","
  fi
fi

token="Bearer $(python $DOCRIVER_GW_HOME/server/token_issue.py --keystore $keystore_file  --password $keystore_password --resource document --expires 300 --subject $USER --permissions txType:submit resourceType:$resource_type resourceId: $resourceId documentCount:1)"

cat << EOF > /tmp/manifest.json
{
    "tx": "${tx_id}",
    "realm": "${realm}",
    "authorization": "${token}",
    "documents": [
        {
            "document": "${doc_id}",
            "type": "${doc_type}",

            $replaces_content

            "properties": {
                "filename": "$(basename "$input_file")"
            },

            "content": {
                $mime_content
                $file_content
            },

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
    ]
}
EOF

rm -f /tmp/response.json
http_response=$(curl -s -X POST -o /tmp/response.json -H 'Content-Type: application/json' -H "Accept: application/json" -w "%{response_code}" --data "@/tmp/manifest.json" "$server_url")
if [ $http_response != "200" ]; then
    echo "Error: $http_response"
    cat /tmp/response.json
else
    cat /tmp/response.json | jq
fi
echo


# curl -v -F key1=value1 -F upload=@localfilename URL
# curl -H "Content-Type: multipart/mixed" -F "request={"param1": "value1"};type=application/json" -F "file1=@2.xml" -F "file2=@2.pdf"
