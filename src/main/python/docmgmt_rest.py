from flask import Flask, jsonify, request, abort
import mysql.connector
from minio import Minio
from document_ingest import validate as validate_document, ingest as ingest_document
import argparse
import logging
from exceptions import ValidationException

app = Flask(__name__)

def init_db():
    global cnx
    cnx = mysql.connector.pooling.MySQLConnectionPool(pool_name='docriver', pool_size=args.dbPoolSize,
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

def parse_args():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument("--objUrl", help="URL of the object store", default='localhost:9000')
    parser.add_argument("--objAccessKey", help="Access key of the object store", default='docriver-key')
    parser.add_argument("--objSecretKey", help="Secret key for the object store", default='docriver-secret')
    parser.add_argument("--bucket", help="Bucket name where the documents are stored", default='docriver')

    parser.add_argument("--rawFileMount", help="mount point of the shared filesystem where raw documents is stored", default='.')
    parser.add_argument("--untrustedFileMount", help="mount point of a filesystem where untrusted files are staged for validations, virus scans, etc", default='.')
    
    parser.add_argument("--dbPoolSize", help="Connection pool size", type=int, default=5)
    parser.add_argument("--dbHost", help="Database host name", default='127.0.0.1')
    parser.add_argument("--dbPort", type=int, help="Database port number", default=3306)
    parser.add_argument("--dbUser", help="Database user name", default='docriver')
    parser.add_argument("--dbPassword", help="Database password", default='docriver')
    parser.add_argument("--dbDatabase", help="Database name", default='docriver')

    parser.add_argument("--log", help="log level (valid values are INFO, WARNING, ERROR, NONE", default='INFO')

    args = parser.parse_args()
    # TODO add validation

@app.errorhandler(ValidationException)
def handle_validation_error(e):
    return str(e), 400

@app.errorhandler(Exception)
def handle_internal_error(e):
    logging.error(e, exc_info=True)
    return str(e), 500

def db_health():
    connection = cnx.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(('SELECT 1 FROM DUAL'))
        cursor.fetchone()
        return True
    except Exception:
        return False
    finally:
        cursor.close()
        connection.close()

@app.route('/document/health', methods=['GET'])
def get_health():
    db_healthy = db_health()
    minio_healthy = minio.bucket_exists(args.bucket)
    healthy_overall = db_healthy and minio_healthy
    return jsonify({'status': 'UP' if healthy_overall else 'DOWN', 
                    'db': db_healthy, 'minio': minio_healthy})

@app.route('/document', methods=['POST', 'PUT'])
def ingest():
    payload = request.json
    logging.info("Received transaction: {}/{}".format(payload['realm'], payload['txId']))
    validate_document(payload)
    tx_id = ingest_document(cnx, minio, args.bucket, args.rawFileMount, args.untrustedFileMount, payload)
    return jsonify({'status': 'ok', 'ref': tx_id})

if __name__ == '__main__':
    parse_args()

    logging.getLogger().setLevel(args.log)

    init_db()
    init_obj_store()

    app.run(debug=True)