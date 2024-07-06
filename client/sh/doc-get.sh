#!/usr/bin/env bash

rawurlencode() {
  local string="${1}"
  local strlen=${#string}
  local encoded=""
  local pos c o

  for (( pos=0 ; pos<strlen ; pos++ )); do
     c=${string:$pos:1}
     case "$c" in
        [-_.~a-zA-Z0-9] ) o="${c}" ;;
        * )               printf -v o '%%%02x' "'$c"
     esac
     encoded+="${o}"
  done
  echo "${encoded}"    # You can either set a return variable (FASTER) 
  REPLY="${encoded}"   #+or echo the result (EASIER)... or both... :p
}

doc_id=
output_path=
realm=p123456
server_url=http://localhost:5000/document
keystore_file=$HOME/.ssh/docriver/docriver.p12
keystore_password=docriver
insecure=

OPTIONS="hd:u:k:w:r:o:n"
OPTIONS_DESCRIPTION=$(cat << EOF
<Option(s)>....
    -h: prints this help message
    -d <DOC_ID>: document id. Mandatory
    -u <SERVER_URL>: URL of the document server REST service. Default: $server_url
    -k <AUTH_KEY_FILE> the keystore file that contains the key for signing the JWT auth token. Default $keystore_file
    -w <AUTH_KEY_PASSWORD> the keystore file password. Default: $keystore_password
    -r <REALM> document realm. Default: $realm
    -o <OUTPUT_PATH> full path name where the downloaded document is written to. Mandatory
    -n don't verify the server's TLS certificate
EOF
)

while getopts $OPTIONS opt; do
  case "${opt}" in
    d)
      doc_id="$OPTARG"
      ;;
    o)
      output_path="$OPTARG"
      ;;
    u)
      server_url="$OPTARG"
      ;;
    k)
      keystore_file="$OPTARG"
      ;;
    w)
      keystore_password="$OPTARG"
      ;;
    r)
      realm="$OPTARG"
      ;;
    n)
      insecure="--insecure"
      ;;
    ?|h)
      echo "Usage: $(basename $0) $OPTIONS_DESCRIPTION"
      exit 0
      ;;
  esac
done
shift "$(($OPTIND -1))"

if [ -z "$doc_id" ]; then
  echo "Documemnt name is mandatory"
  exit 1
fi

if [ -z "$output_path" ]; then
  echo "Output path is mandatory"
  exit 1
fi

token="Bearer $(python $DOCRIVER_GW_HOME/src/token_issue.py --keystore $keystore_file  --password $keystore_password --resource document --expires 300 --subject $USER --permissions txType:get-document 'document:.*')"

rm -f $output_path
curl $insecure --fail-with-body -s -X GET -o $output_path -H "Authorization:$token" "${server_url}/${realm}/$(rawurlencode $doc_id)"
if [ $? -ne 0 ]; then
  cat $output_path
  echo
  exit 1
fi

ls -al $output_path

# curl http://www.example.com/data.txt -O -J 