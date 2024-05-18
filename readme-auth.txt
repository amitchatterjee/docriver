
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

# Run the token server using docker
docker run -it --rm --name docriver-token --network dev --user=1000:1000 -v $DOCRIVER_GW_HOME/src:/app -v $HOME/.ssh/docriver:/keystore -p 5001:5001 docriver-base:0.0.1-SNAPSHOT python /app/reference_token_server.py --keystore  /keystore/docriver.p12 --password docriver --log INFO --debug
 * Serving Flask app 'reference_token_server'

# Test token server
curl -u docriver:docriver -s -X POST -H 'Content-Type: application/json' -H "Accept: application/json" --data '
    {"subject": "amit", 
     "audience": "docriver", 
     "permissions": {"txType": "submit", "resourceType": "claims", "documentCount": 10}}' \
http://localhost:8080/token