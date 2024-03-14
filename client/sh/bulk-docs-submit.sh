#!/usr/bin/env bash

realm=p123456
tx_id=$(date +%s)
input_folder=
file_selection_regex=".+\.(zip|png|jpg|jpeg|xml|json|pdf)"

resource_type='claim'
resource_id='123456789'
resource_description='blah blah blah'
command=submit
realm=p123456
server_url=http://localhost:5000/tx
verbose=
doc_type="General"
keystore_file=$HOME/.ssh/docriver/docriver.p12
keystore_password=docriver

OPTIONS="ht:f:x:r:i:p:u:vy:k:w:"
OPTIONS_DESCRIPTION=$(cat << EOF
<Option(s)>....
    -h: prints this help message
    -t <TX_ID>: transaction id. Default (generated from timestamp): $tx_id
    -f <INPUT_FILE>: input folder - Mandatory
    -x <FILE_SELECTION_REGEX>: regex to select files from folder. Default: $file_selection_regex
    -r <REF_RESOURCE_TYPE>: reference resource type. Default: $resource_type
    -i <REF_RESOURCE_ID>: reference resource id. Default: $resource_id
    -p <REF_RESOURCE_DESCRIPTION>: reference resource description. Default: $resource_description
    -u <SERVER_URL>: URL of the document server REST service. Default: $server_url
    -v: for verbose and debug output
    -y <TYPE>: document type. Default: $doc_type
    -k <AUTH_KEY_FILE> the keystore file that contains the key for signing the JWT auth token
    -w <AUTH_KEY_PASSWORD> the keystore file password
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
    v) verbose="-v --progress-bar"
      ;;
    y)
      doc_type="$OPTARG"
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

if [ -z "$input_folder" ]; then
    echo "Input folder must be specified"
    exit 1
fi

token="Bearer $(python $DOCRIVER_GW_HOME/server/token_issue.py --keystore $keystore_file  --password $keystore_password --resource document --expires 300 --subject $USER --permissions realm:$realm resourceType:$resource_type resourceId: $resourceId documentCount:1000)"

files=$(ls -1 $input_folder | grep -v -E '\s' | grep -i -E "$file_selection_regex"  | grep -v manifest.json)

ts=$(date +%s)
files=$(find  $input_folder -maxdepth 1 -regextype posix-egrep -regex "$file_selection_regex" | grep -v -E '\s' | grep -v manifest.json)
manifest=$(for file in $files; do
  file_name=$(basename "$file")
  file_name_no_ext=${file_name%.*}
  extension="${file_name##*.}"
  jq -n --arg fname "$file_name" '{path: $fname}' \
    | jq -n --arg docid "${file_name_no_ext}-${ts}" --arg type "${doc_type}" --arg filename "${file_name}" \
        '{document: $docid, type: $type, content: inputs, properties: {filename: $filename}}'
done | jq -n --arg tx "$tx_id" --arg realm "$realm" --arg token "$token" '{tx: $tx, authorization: $token, realm: $realm, documents: [inputs]}' \
     | jq -n --arg rsrcid "$resource_id" --arg rsrctyp "$resource_type" --arg rsrcdesc "$resource_description"  'inputs + {references:[{resourceType: $rsrctyp, resourceId: $rsrcid, description: $rsrcdesc}]}'
)

echo $manifest > /tmp/manifest.json

params=()
params+=(-F "files=@/tmp/manifest.json")
for file in $files; do
  params+=(-F "files=@${file}")
done
# echo "${params[@]}"
curl $verbose -s -H "Accept: text/html" "${params[@]}" "$server_url" | lynx -dump -stdin
echo

# curl -v -F key1=value1 -F upload=@localfilename URL
# curl -H "Content-Type: multipart/mixed" -F "request={"param1": "value1"};type=application/json" -F "file1=@2.xml" -F "file2=@2.pdf"
