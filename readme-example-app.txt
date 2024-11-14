
# Create htpasswd file - this is only needed if basic authentication is being used
echo docriver:$(echo 'docriver' | openssl passwd -apr1 -stdin) > $DOCRIVER_GW_HOME/infrastructure/nginx/conf/htpasswd

# Setup OKTA. Needed for openid/oauth2 SSO
1. Create OKTA developer account.
2. Login to https://dev-XXXX.admin.okta.com
2. Navigate to Applications->Applications->Create App Integration:
    Name: docriver
    Redirect URIs:
        https://localhost/redirect
        https://gateway.quik-j.com/redirect
    Sign-out redirect URIs: 
        https://localhost
        https://gateway.quik-j.com
3. Navigate to Directory->Profile Editor->Profile Editor->user (default):
    Add attribute: docriverPermissions
4. Navigate to Directory->Profile Editor->Profile Editor->docriver (oidc_client):
    Add attribute: docriverPermissions
    Add mapping: user.docriverPermissions -> appuser.docriverPermissions
5: Navigate to Security->API->Authorization Servers->default
    Add claim: docriverPermissions
        Include in token type: AccessToken
        Value type: expression
        Value: appuser.docriverPermissions
        Include in: Profile

# Create TLS key and certificate for https access
openssl genrsa -out $HOME/.ssh/docriver/exampleapp-nginx.key 4096

# Important: Make sure that the CN matches the hostname
openssl req -new -key $HOME/.ssh/docriver/exampleapp-nginx.key -nodes -subj "/C=US/ST=NC/L=Apex/O=Docriver Security/OU=R&D Department/CN=gateway.quik-j.com" -out $HOME/.ssh/docriver/exampleapp-nginx.csr

# Enter the CA's secret key - see the readme-development.txt
openssl x509 -req -in $HOME/.ssh/docriver/exampleapp-nginx.csr -CA $HOME/.ssh/quik-CA.pem -CAkey $HOME/.ssh/quik-CA.key -CAcreateserial -out $HOME/.ssh/docriver/exampleapp-nginx.crt -days 825 -sha256 -extfile $DOCRIVER_GW_HOME/infrastructure/nginx/conf/x509-cert-exampleapp.ext

# Start the components
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-example-app.yml -p docriver up --detach

# From a browser
https://gateway.quik-j.com/
or:
https://localhost/