export DOCRIVER_GW_HOME=$HOME/git/docriver-gateway
export DOCRIVER_UNTRUSTED_ROOT=$HOME/storage/docriver/untrusted

export DOCRIVER_MYSQL_USER=docriver
export DOCRIVER_MYSQL_PASSWORD=docriver
export DOCRIVER_MYSQL_ROOT_PASSWORD=docriver
export DOCRIVER_MYSQL_HOST=127.0.0.1
export DOCRIVER_MYSQL_PORT=3306
export DOCRIVER_MYSQL_VERSION=8.2

export DOCRIVER_MINIO_VERSION=RELEASE.2023-12-23T07-19-11Z.fips
export DOCRIVER_MINIO_CONSOLE_PORT=9001
export DOCRIVER_MINIO_PORT=9000

export DOCRIVER_CLAMAV_VERSION=stable_base
export DOCRIVER_CLAMAV_PORT=3310

export DOCRIVER_NGINX_VERSION=latest
export DOCRIVER_NGINX_PORT=8443

export EXAMPLE_APP_NGINX_PORT=443

# Make changes as needed. Many of these settings will need to match with the OIDC and proxy settings. Example - 
# OIDC/OAUTH2 settings:
# export DOCRIVER_OIDC_CLIENTID="XXXXXX"
# export DOCRIVER_OIDC_SECRET="YYYYYY"
# export DOCRIVER_OIDC_DISCOVERY_URL="https://dev-XXXXX.okta.com/oauth2/default/.well-known/openid-configuration"
# export DOCRIVER_OIDC_REDIRECT_URL="https://gateway.quik-j.com/redirect"
# export DOCRIVER_AUTH_URL="https://dev-XXXXXX.okta.com/oauth2/default"
# export DOCRIVER_OIDC_POST_LOGOUT_REDIRECT_URL="https://gateway.quik-j.com"
# Proxy settings:
# export DOCRIVER_MINIO_CONSOLE_URL="https://docriver.quik-j.com/minio/console"

export DOCRIVER_OIDC_CLIENTID=
export DOCRIVER_OIDC_SECRET=
export DOCRIVER_OIDC_DISCOVERY_URL=
export DOCRIVER_OIDC_REDIRECT_URL=
export DOCRIVER_AUTH_URL=
export DOCRIVER_MINIO_CONSOLE_URL=

export PATH=$PATH:$DOCRIVER_GW_HOME/infrastructure/sh:$DOCRIVER_GW_HOME/client/sh:$DOCRIVER_GW_HOME/server
