
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
openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 -subj "/C=US/ST=NC/L=Apex/O=Docriver Security/OU=R&D Department/CN=docriver.quik-j.com" -keyout $HOME/.ssh/docriver/nginx.key -out $HOME/.ssh/docriver/nginx.crt

# Start the components
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-example-app.yml -p docriver up --detach

# From a browser
https://localhost/