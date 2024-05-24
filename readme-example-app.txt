
# Create htpasswd file
echo docriver:$(echo 'docriver' | openssl passwd -apr1 -stdin) > $DOCRIVER_GW_HOME/infrastructure/nginx/conf/htpasswd

# Create TLS key and certificate
openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 -subj "/C=US/ST=NC/L=Apex/O=Docriver Security/OU=R&D Department/CN=docriver.quik-j.com" -keyout $HOME/.ssh/docriver/nginx.key -out $HOME/.ssh/docriver/nginx.crt

# Start the components
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-example-app.yml -p docriver up --detach

