
# Create htpasswd file - this is only needed if basic authentication is being used
echo docriver:$(echo 'docriver' | openssl passwd -apr1 -stdin) > $DOCRIVER_GW_HOME/infrastructure/nginx/conf/htpasswd

# Setup OKTA. Needed for openid/oauth2 SSO
1. Create OKTA developer account.
2. Login to https://dev-XXXX.admin.okta.com
2. Navigate to Applications->Applications->Create App Integration:
    Name: docriver
    Redirect URIs:
        https://localhost:8443/redirect
        https://appeals.quik-j.com:8443/redirect
    Sign-out redirect URIs: 
        https://localhost:8443
        https://appeals.quik-j.com:8443
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
6: To $HOME/.bashrc
    export DOCRIVER_OIDC_CLIENTID="XXXXXX"
    export DOCRIVER_OIDC_SECRET="YYYYYY"
    export DOCRIVER_OIDC_DISCOVERY_URL="https://dev-XXXXX.okta.com/oauth2/default/.well-known/openid-configuration"
    export DOCRIVER_OIDC_REDIRECT_URL="https://appeals.quik-j.com:8443/redirect"
    export DOCRIVER_AUTH_URL="https://dev-XXXXXX.okta.com/oauth2/default"
    export DOCRIVER_OIDC_POST_LOGOUT_REDIRECT_URL="https://appeals.quik-j.com:8443"

# Create TLS key and certificate for https access
openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 -subj "/C=US/ST=NC/L=Apex/O=Docriver Security/OU=R&D Department/CN=docriver.quik-j.com" -keyout $HOME/.ssh/docriver/nginx.key -out $HOME/.ssh/docriver/nginx.crt

# Start the components
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-example-app.yml -p docriver up --detach
