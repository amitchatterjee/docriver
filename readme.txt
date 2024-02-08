#######################################################
# One time setup
#######################################################
docker network create dl

# Install python dependencies
pip install flask mysql-connector-python minio file-validator flask-accept flask-cors fleep

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
mkdir -p ~/storage/docriver/raw/p123456/

#######################################################
# Run components
#######################################################
# Start infrastructure components needed for the document repo server
docker compose -f $HOME/git/docriver/src/main/compose/docker-compose.yml -p docriver up --detach

# Run Document Manager Server REST
python $HOME/git/docriver/src/main/python/docmgmt_http.py --rawFileMount $HOME/storage/docriver/raw --untrustedFileMount $HOME/storage/docriver/untrusted

#######################################################
# Execute
#######################################################
# Document ingestion using the docriver CLI tool. Use -h for options

# Inline document ingestion
$HOME/git/docriver/src/test/sh/doc-submit-rest.sh -m 'application/pdf' -y payment-receipt -r claim -i C1234567 -p "Proof of payment" -f ~/Downloads/wakemed-payment.pdf

# Ingestion from raw file mount
$HOME/git/docriver/src/test/sh/doc-submit-rest.sh -m 'application/pdf' -y payment-receipt -r claim -i C1234567 -p "Proof of payment" -f ~/Downloads/wakemed-payment.pdf -b $HOME/storage/docriver/raw

# Cleanup
mc rm --recursive --force docriver/docriver/p123456
echo 'DELETE FROM TX'| mysql -h 127.0.0.1 -u docriver -p docriver

# Access the data
mysql -h 127.0.0.1 -u docriver -p docriver

#######################################################
# Virus Scan
#######################################################
mkdir -p $HOME/storage/clamav/sockets
mkdir -p $HOME/storage/clamav/signaturedb
chmod -R a+rwx $HOME/storage/clamav/sockets $HOME/storage/clamav/signaturedb

# Virus scanner with clamav server and clamdscan client
docker run -it --rm --name clamav -p 3310:3310 --mount type=bind,source=$HOME/storage/docriver/untrusted,target=/scandir --volume $HOME/storage/clamav/signaturedb:/var/lib/clamav --mount type=bind,source=$HOME/storage/clamav/sockets/,target=/tmp/ clamav/clamav:stable_base

docker run -it --rm --name clamdscan --mount type=bind,source=$HOME/storage/docriver/untrusted,target=/scandir --mount type=bind,source=$HOME/storage/clamav/sockets/,target=/tmp clamav/clamav:stable_base clamdscan --fdpass --verbose --stdout /scandir/cheetah

# Virus scanner with clamscan - this does not require server but it likely to be slower
docker run -it --rm --name clamscan --mount type=bind,source=$HOME/storage/docriver/untrusted,target=/scandir --volume $HOME/storage/clamav/signaturedb:/var/lib/clamav clamav/clamav:stable_base clamscan /scandir/cheetah
