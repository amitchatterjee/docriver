
# Create htpasswd file
echo docriver:$(echo 'docriver' | openssl passwd -apr1 -stdin) > $DOCRIVER_GW_HOME/infrastructure/nginx/conf/htpasswd
