import mysql.connector
from minio import Minio
import argparse
import logging
import clamd
import controller.http as http

def init_db():
    global connection_pool
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(pool_name='docriver', pool_size=args.dbPoolSize,
            user=args.dbUser, password=args.dbPassword,
            host=args.dbHost,
            port=args.dbPort,
            database=args.dbDatabase)

def init_obj_store():
    global minio 
    # TODO fix the secure=False
    minio = Minio(args.objUrl, secure=False,
        access_key=args.objAccessKey,
        secret_key=args.objSecretKey)
    
def init_virus_scanner():
    global scanner
    scanner = clamd.ClamdNetworkSocket(host=args.scanHost, port=args.scanPort)

def parse_args():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument("--objUrl", help="URL of the object store", default='localhost:9000')
    parser.add_argument("--objAccessKey", help="Access key of the object store", default='docriver-key')
    parser.add_argument("--objSecretKey", help="Secret key for the object store", default='docriver-secret')
    parser.add_argument("--bucket", help="Bucket name where the documents are stored", default='docriver')

    parser.add_argument("--rawFilesystemMount", help="mount point of the shared filesystem where raw documents is stored by applications. The applications can copy files to this location and specify the location instead of uploading", default='.')
    parser.add_argument("--untrustedFilesystemMount", help="mount point of a shared filesystem where untrusted files are staged for validations, virus scans, etc. This mount point must be shared with the virus scanner", default='.')
    
    parser.add_argument("--dbPoolSize", help="Connection pool size", type=int, default=5)
    parser.add_argument("--dbHost", help="Database host name", default='127.0.0.1')
    parser.add_argument("--dbPort", type=int, help="Database port number", default=3306)
    parser.add_argument("--dbUser", help="Database user name", default='docriver')
    parser.add_argument("--dbPassword", help="Database password", default='docriver')
    parser.add_argument("--dbDatabase", help="Database name", default='docriver')

    parser.add_argument("--scanHost", help="Document virus checker hostname", default='127.0.0.1')
    parser.add_argument("--scanPort", type=int, help="Document virus checker port number", default=3310)
    parser.add_argument("--scannerFileMount", help="Mount point for the untrusted area in the scanner server", default='/scandir')

    parser.add_argument("--log", help="log level (valid values are INFO, WARNING, ERROR, NONE", default='INFO')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args()
    # TODO add validation

if __name__ == '__main__':
    parse_args()
    logging.getLogger().setLevel(args.log)
    init_db()
    init_obj_store()
    init_virus_scanner()

    http.process_requests(args, connection_pool, minio, scanner)

