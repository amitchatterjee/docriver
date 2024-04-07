
# Test token issue and token validation for submission

# Issue a token from realm: p123456
token=$(python $DOCRIVER_GW_HOME/src/token_issue.py --keystore $HOME/.ssh/docriver/test123456.p12  --password docriver --resource document --expires 300 --subject $USER --permissions txType:submit resourceType:claims documentCount:10)

echo $token

# Validate the token using docriver keystore
python $DOCRIVER_GW_HOME/src/token_decode.py --keystore $HOME/.ssh/docriver/truststore.p12 --password docriver --token "$token"

# Token for get-document operation
python $DOCRIVER_GW_HOME/src/token_issue.py --keystore $HOME/.ssh/docriver/docriver.p12  --password docriver --resource document --expires 300 --subject $USER --permissions txType:get-document document:doc-1
