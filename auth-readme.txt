# Create a key pair + x509 certificate for docriver
$DOCRIVER_GW_HOME/infrastructure/dev/sh/create_certs.sh docriver

# Create cerificate for each realm in the system
$DOCRIVER_GW_HOME/infrastructure/dev/sh/create_certs.sh p123456
$DOCRIVER_GW_HOME/infrastructure/dev/sh/create_certs.sh test123456

# Copy all the certificates into the docrive keystore
cat $HOME/.ssh/docriver.crt $HOME/.ssh/p123456.crt $HOME/.ssh/test123456.crt > $HOME/.ssh/all.crt
openssl pkcs12 -export -name "docriver" \
    -out $HOME/.ssh/docriver.p12 -inkey $HOME/.ssh/docriver.key -in $HOME/.ssh/all.crt

----------------------
# Issue a token from realm: p123456
token=$(python $DOCRIVER_GW_HOME/server/token_issue.py --keystore $HOME/.ssh/p123456.p12  --password docriver --resource document --expires 300 --subject someoneabc --permissions realm:p123456 resourceType:claims)

echo $token

# Authorize the token using docriver keystore
python $DOCRIVER_GW_HOME/server/token_validate.py --keystore $HOME/.ssh/docriver.p12 --password docriver --token "$token"
