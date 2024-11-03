#######################################################
# One time setup
#######################################################
# Install docker

docker network create dev

# Install jq
sudo dnf install -y jq

# Create python venv
cd $HOME
python -m venv docriver-venv

# Add to ~/.bashrc
# Change the line below to point to the root of the docriver source 
export DOCRIVER_GW_HOME=$HOME/git/docriver-gateway
source $DOCRIVER_GW_HOME/env.sh
source $HOME/docriver-venv/bin/activate
# If you need to override some of the default properties in env.sh, add them to ~/.bashrc
# Exit the shell and create a new one before continuing further

# Install python dependencies
pip install -r $DOCRIVER_GW_HOME/docker/requirements.txt

# Install pytest
pip install -U pytest pytest-cov

# Install pkg build
pip install build

### Strictly, you don't need the clients to be installed because they can be executed from the docker images. This is more of a convenience.

# Install minio client
sudo curl https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
sudo chmod +x /usr/local/bin/mc

# Install MYSQL client
sudo dnf install mysql

# TODO - automate this. See https://github.com/minio/minio/blob/master/docs/docker/README.md
# Setup storage buckets, etc. You need to do this whenever you delete the docker volume
    1. Open minio console: http://localhost:9001 (or https://gateway.quik-j.com/minio/console - if you are using an ingress)
        login: minioadmin/minioadmin
    2. From console, create acess key - docriver-key/docriver-secret
    3. Create a bucket - docriver
    4. Setup access from mc
        mc alias set docriver http://localhost:9000 docriver-key docriver-secret
        mc admin info docriver

# Create storage area
mkdir -p $HOME/storage/docriver/raw/p123456/

# Add keys and certificates for token verification
rm $HOME/.ssh/docriver/*
# Create a key pair + x509 certificate for docriver (master) key + cert.
dr-create-certs.sh master $HOME/.ssh/docriver

# Create a key pair + x509 certificate for docriver (master) key + cert.
dr-create-certs.sh docriver $HOME/.ssh/docriver

# Create key + x509 cert for each realm in the system
dr-create-certs.sh p123456 $HOME/.ssh/docriver
dr-create-certs.sh test123456 $HOME/.ssh/docriver

# Copy all the certificates into the docrive keystore and with the docriver private key
cat $HOME/.ssh/docriver/master.crt $HOME/.ssh/docriver/docriver.crt $HOME/.ssh/docriver/p123456.crt $HOME/.ssh/docriver/test123456.crt > $HOME/.ssh/docriver/truststore.crt
openssl pkcs12 -export -name "docriver" -out $HOME/.ssh/docriver/truststore.p12 -inkey $HOME/.ssh/docriver/master.key -in $HOME/.ssh/docriver/truststore.crt

openssl pkcs12 -info -in $HOME/.ssh/docriver/truststore.p12 -passin pass:docriver

# Install and setup for Visual Code debugging
pip install debugpy

# Add debug configuration ($DOCRIVER_GW_HOME/.vscode/launch.json)
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Attach",
            "type": "debugpy",
            "request": "attach",
            "connect": {
              "host": "localhost",
              "port": 5678
            }
          }
    ]
}

#######################################################
# Build and install packages
#######################################################
# Build all packages
build-packages.sh

# Build individual packages
cd $DOCRIVER_GW_HOME/auth
python -m build --wheel

# Install a package
pip install --force-reinstall dist/docriver_auth-1.0.0b0-py3-none-any.whl

#######################################################
# Build the docker containers
#######################################################

# Make sure you build the packages first. All wheel archives are automatically installed on the server
build-docker.sh docriver-base

build-docker.sh nginx-opentel

#######################################################
# Start infrastructure components
#######################################################
# Start backend components needed for the document repo server
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-backend.yml -p docriver up --detach

#######################################################
# Start gateway
#######################################################
# Start the docker gateway docker containers - Note that this is not needed if you want to run the gateway by executing the python commands shown below.
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-gateway.yml -p docriver up --detach

# Run the gateway
python $DOCRIVER_GW_HOME/server/src/docriver_server/gateway.py --rawFilesystemMount $HOME/storage/docriver/raw --untrustedFilesystemMount $HOME/storage/docriver/untrusted --authKeystore $HOME/.ssh/docriver/truststore.p12 --authPassword docriver --debug

# Run the gateway with remote debugging
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client $DOCRIVER_GW_HOME/server/src/docriver_server/gateway.py --rawFilesystemMount $HOME/storage/docriver/raw --untrustedFilesystemMount $HOME/storage/docriver/untrusted --debug

#######################################################
# Execute clients
#######################################################
# Document ingestion using the docriver CLI tool. Use -h for options

# To connect to a server with self-signed certificate, append the following additional parameters (change as needed) to the commands below:
-u "https://localhost:5000/tx" -n

# Inline document ingestion using the drc client
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug submit --method inline --source $DOCRIVER_GW_HOME/server/test/resources/documents/test123456/sample.pdf --documentType "receipt" --resourceType claim --resourceId C1234567 --resourceDescription 'Proof of payment'


# Ingestion from raw file mount using the drc client
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug submit --method copy --source $DOCRIVER_GW_HOME/server/test/resources/documents/test123456/sample.pdf --documentType "receipt" --resourceType claim --resourceId C1234567 --resourceDescription 'Proof of payment' --rawFilesystemMount $HOME/storage/docriver/raw

# Ingestion using scp using the drc client - change the XXX, YYY, HHHH, etc.
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug submit --method scp --source $DOCRIVER_GW_HOME/server/test/resources/documents/test123456/sample.pdf --documentType "receipt" --resourceType claim --resourceId C1234567 --resourceDescription 'Proof of payment' --scpUser XXX --scpPassword YYYY --scpHost HHHH --autoAddHostKey --scpPath ~/storage/docriver/raw

# Multipart form file ingestion using the drc client
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug submit --source $HOME/cheetah --documentType "Flickr images" --prefix "$(date '+%Y-%m-%d-%H-%M-%S')/" --resourceType image --resourceId 123 --resourceDescription 'upload from flickr'

# Virus scan failure
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug submit --method copy --source $DOCRIVER_GW_HOME/server/test/resources/documents/test123456/eicar.txt --documentType "receipt" --resourceType claim --resourceId C1234567 --resourceDescription 'Proof of payment' --rawFilesystemMount $HOME/storage/docriver/raw

# Download a document - NOTE: change the document number and output path name
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug get document --name "2024-09-30-12-20-55/52946576006_420234d4f2_c.jpg-1727713256" --output /tmp

# Cleanup
dr-scrub.sh

# Access the metadata
mysql -h 127.0.0.1 -u docriver -p docriver

#######################################################
# Run tests
#######################################################
cd $DOCRIVER_GW_HOME/server
# Run all tests
python -m pytest --cov -rPX -vv

# Run one file or one test
python -m pytest --cov -rPX -vv 'test/functional/test_rest_doc_transactions.py::test_ref_document'

#### Don't use the --cov option as this modifies the complied code and as a result, breakpoints won't hit

# Run tests with remote debugging
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m pytest -rPX -vv 

#######################################################
# Scaling
#######################################################
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-gateway.yml -p docriver up -d --scale docriver-gateway=2 --no-recreate
