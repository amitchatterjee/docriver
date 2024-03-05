import mysql.connector
from minio import Minio
import argparse
import logging
import clamd
import sys
import os

from controller.http import init_app, init_params

def init_db(host, port, db, user, password, pool_size):
    return mysql.connector.pooling.MySQLConnectionPool(pool_name='docriver', 
            pool_size=pool_size,
            user=user, password=password,
            host=host,
            port=port,
            database=db)

def init_obj_store(url, access_key, secret_key):
    # TODO fix the secure=False
    return Minio(url, secure=False, access_key=access_key, secret_key=secret_key)
    
def init_virus_scanner(host, port):
    return clamd.ClamdNetworkSocket(host=host, port=port)

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--httpPort", type=int, help="HTTP port number", default=5000)

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
    parser.add_argument("--scannerFilesystemMount", help="Mount point for the untrusted area in the scanner server", default='/scandir')

    parser.add_argument("--log", help="log level (valid values are INFO, WARNING, ERROR, NONE", default='INFO')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args(args)
    # TODO add validation

    return args

if __name__ == '__main__':
    args = parse_args(sys.argv[1:])
    logging.getLogger().setLevel(args.log)
    connection_pool = init_db(args.dbHost, args.dbPort, args.dbDatabase, args.dbUser, args.dbPassword, args.dbPoolSize)
    minio = init_obj_store(args.objUrl, args.objAccessKey, args.objSecretKey)
    scanner = init_virus_scanner(args.scanHost, args.scanPort)

    app = init_app()
    init_params(connection_pool, minio, scanner, args.bucket, args.untrustedFilesystemMount, args.rawFilesystemMount, args.scannerFilesystemMount)
    app.run(port=args.httpPort, debug=args.debug)

