#######################################################
# One time setup
#######################################################
# Install docker

docker network create dl

# Install jq
sudo dnf install -y jq

# Create python venv
cd $HOME
python -m venv docriver-venv

# Add to ~/.bashrc
# Change the line below to point to the root of the docriver source 
export DOCRIVER_GW_HOME=$HOME/git/docriver
# Make changes to the env.sh file if needed
source $DOCRIVER_GW_HOME/env.sh
source ~/docriver-venv/bin/activate
# Exit the shell and create a new one before continuing further

# Install python dependencies
pip install -r $DOCRIVER_GW_HOME/server/docker/requirements.txt

# Install pytest
pip install -U pytest pytest-cov

### Strictly, you don't need the clients to be installed because they can be executed from the docker images. This is more of a convenience.

# Install minio client
sudo curl https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
sudo chmod +x /usr/local/bin/mc

# Install MYSQL client
sudo dnf install mysql

# TODO - automate this. See https://github.com/minio/minio/blob/master/docs/docker/README.md
# Setup storage buckets, etc. You need to do this whenever you delete the docker volume
    1. Open minio console: http://localhost:9001
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
$DOCRIVER_GW_HOME/infrastructure/sh/create_certs.sh master $HOME/.ssh/docriver

# Create a key pair + x509 certificate for docriver (master) key + cert.
$DOCRIVER_GW_HOME/infrastructure/sh/create_certs.sh docriver $HOME/.ssh/docriver

# Create key + x509 cert for each realm in the system
$DOCRIVER_GW_HOME/infrastructure/sh/create_certs.sh p123456 $HOME/.ssh/docriver
$DOCRIVER_GW_HOME/infrastructure/sh/create_certs.sh test123456 $HOME/.ssh/docriver

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
# Start components
#######################################################
# Start infrastructure components needed for the document repo server
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose.yml -p docriver up --detach

# Run the HTTP Endpoint without Authorization
python $DOCRIVER_GW_HOME/server/main.py --rawFilesystemMount $HOME/storage/docriver/raw --untrustedFilesystemMount $HOME/storage/docriver/untrusted --debug

# Run the HTTP Endpoint with Authorization
python $DOCRIVER_GW_HOME/server/main.py --rawFilesystemMount $HOME/storage/docriver/raw --untrustedFilesystemMount $HOME/storage/docriver/untrusted --authKeystore $HOME/.ssh/docriver/truststore.p12 --authPassword docriver --debug

# Run the HTTP Endpoint with remote debugging
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client main.py --rawFilesystemMount $HOME/storage/docriver/raw --untrustedFilesystemMount $HOME/storage/docriver/untrusted --debug

#######################################################
# Execute
#######################################################
# Document ingestion using the docriver CLI tool. Use -h for options

# Inline document ingestion
$DOCRIVER_GW_HOME/client/sh/doc-submit.sh -m 'application/pdf' -y payment-receipt -r claim -i C1234567 -p "Proof of payment" -m application/pdf -f $DOCRIVER_GW_HOME/server/test/resources/documents/test123456/sample.pdf

# Ingestion from raw file mount
$DOCRIVER_GW_HOME/client/sh/doc-submit.sh -y payment-receipt -r claim -i C1234567 -p "Proof of payment" -b $HOME/storage/docriver/raw -f $DOCRIVER_GW_HOME/server/test/resources/documents/test123456/sample.pdf

# Multipart form file ingestion
$DOCRIVER_GW_HOME/client/sh/bulk-docs-submit.sh -f $HOME/cheetah -y "Flickr images" -e "$(date '+%Y-%m-%d-%H-%M-%S')/"

# Virus scan failure
$DOCRIVER_GW_HOME/client/sh/doc-submit.sh -y payment-receipt -r claim -i C1234567 -p "Proof of payment" -f $DOCRIVER_GW_HOME/server/test/resources/documents/test123456/eicar.txt -b $HOME/storage/docriver/raw

# Cleanup
$DOCRIVER_GW_HOME/infrastructure/sh/scrub.sh

# Access the data
mysql -h 127.0.0.1 -u docriver -p docriver

#######################################################
# Run tests
#######################################################
cd $DOCRIVER_GW_HOME
# Run all tests
python -m pytest --cov -rPX -vv
# Run one test
python -m pytest --cov -rPX -vv 'server/test/functional/test_rest_doc_transactions.py::test_ref_document'

#### Don't use the --cov option as this modifies the complied code and as a result, breakpoints won't hit

# Run tests with remote debugging
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m pytest -rPX -vv 

#######################################################
# Virus Scan - ignore. My scribbles 
#######################################################
# Virus scanner with clamscan - this does not require server but it is slower. Note the use of signaturedb. This is the directory where the signatures are downloaded, stored and refreshed. This is important to setup. Otherwise, there will be a long download everytime clamscan is called. This will be very slow and will also result in rate-limiting from the sites where the signatures are downloaded 
mkdir -p $HOME/storage/clamav/signaturedb
chmod -R a+rwx $HOME/storage/clamav/signaturedb

# clamscan
docker run -it --rm --network dl --name clamscan --mount type=bind,source=$HOME/storage/docriver/untrusted,target=/scandir --volume $HOME/storage/clamav/signaturedb:/var/lib/clamav clamav/clamav:stable_base clamscan /scandir/<DIR_TOSCAN>
