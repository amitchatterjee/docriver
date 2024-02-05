#!/usr/bin/env bash

realm=p123456
tx_id=$(date +%s)
input_folder=
file_selection_regex=".+\.(zip|png|jpg|jpeg|xml|json|pdf)"

resource_type='claim'
resource_id='123456789'
resource_description='blah blah blah'
operation=i
command=submit
realm=p123456
server_url=http://localhost:5000/rest/document

OPTIONS="ht:f:x:r:i:p:u:"
OPTIONS_DESCRIPTION=$(cat << EOF
<Option(s)>....
    -h: prints this help message
    -t <TX_ID>: transaction id. Default (generated from timestamp): $tx_id
    -f <INPUT_FOLDER>: input folder - Mandatory
    -x <FILE_SELECTION_REGEX>: regex to select files from folder. Default: $file_selection_regex
    -r <REF_RESOURCE_TYPE>: reference resource type. Default: $resource_type
    -i <REF_RESOURCE_ID>: reference resource id. Default: $resource_id
    -p <REF_RESOURCE_DESCRIPTION>: reference resource description. Default: $resource_description
    -u <SERVER_URL>: URL of the document server REST service. Default: $server_url
EOF
)

while getopts $OPTIONS opt; do
  case "${opt}" in
    t)
      tx_id="$OPTARG"
      ;;
    f)
      input_folder="$OPTARG"
      ;;
   x)
      file_selection_regex="$OPTARG"
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

if [ -z "$input_folder" ]; then
    echo "Input folder must be specified"
    exit 1
fi

files=$(ls -1 $input_folder | grep -v -E '\s' | grep -i -E "$file_selection_regex"  | grep -v manifest.json)
for file in $files; do
  echo $file
done
exit 0

cat << EOF > /tmp/manifest.json
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
