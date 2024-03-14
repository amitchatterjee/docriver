
# Test token issue and token validation

# Issue a token from realm: p123456
token=$(python $DOCRIVER_GW_HOME/server/token_issue.py --keystore $HOME/.ssh/docriver/test123456.p12  --password docriver --resource document --expires 300 --subject $USER --permissions realm:p123456 resourceType:claims documentCount:10)

echo $token

# Validate the token using docriver keystore
python $DOCRIVER_GW_HOME/server/token_decode.py --keystore $HOME/.ssh/docriver/truststore.p12 --password docriver --token "$token"
