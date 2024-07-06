
# Test token issue and token validation for submission

# Issue a token from realm: p123456
token=$(python $DOCRIVER_GW_HOME/src/token_issue.py --keystore $HOME/.ssh/docriver/test123456.p12  --password docriver --resource document --expires 300 --subject $USER --permissions txType:submit resourceType:claims documentCount:10)

echo $token

# Validate the token using docriver keystore
python $DOCRIVER_GW_HOME/src/token_decode.py --keystore $HOME/.ssh/docriver/truststore.p12 --password docriver --token "$token"

# Token for get-document operation
python $DOCRIVER_GW_HOME/src/token_issue.py --keystore $HOME/.ssh/docriver/docriver.p12  --password docriver --resource document --expires 300 --subject $USER --permissions txType:get-document document:doc-1

# Run token server
python $DOCRIVER_GW_HOME/src/reference_token_server.py --keystore $HOME/.ssh/docriver/docriver.p12  --password docriver --log INFO

# Test token server
curl --insecure -u docriver:docriver -s -X POST -H 'Content-Type: application/json' -H "Accept: application/json" --data '
    {"subject": "amit", 
     "audience": "docriver", 
     "permissions": {"txType": "submit", "resourceType": "claims", "documentCount": 10}}' \
http://localhost:5001/token