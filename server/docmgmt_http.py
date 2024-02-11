from flask import Flask, jsonify, request, send_from_directory
from flask_accept import accept
from flask_cors import CORS
import mysql.connector
from minio import Minio
import argparse
import logging
import os
import shutil
import json
import uuid
import clamd

from exceptions import ValidationException
from document_ingest import validate_manifest, preprocess_manifest, write_metadata, stage_documents_from_manifest, validate_documents, stage_documents_from_form, get_payload_from_form, write_to_obj_store

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def stage_dirname(untrusted_file_mount):
    return "{}/{}".format(untrusted_file_mount, uuid.uuid1())

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

def db_healthcheck():
    connection = connection_pool.get_connection()
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

def health_status(up):
    return "UP" if up else "DOWN"

@app.route('/rest/document', methods=['POST'])
@accept('application/json')
def submit_new_tx_rest():
    payload = request.json
    stage_dir = stage_dirname(args.untrustedFilesystemMount)
    connection = connection_pool.get_connection()
    try:
        os.makedirs(stage_dir)
        logging.info("Received REST ingestion request: {}/{}".format(payload['realm'], payload['txId']))
        validate_manifest(payload)
        preprocess_manifest(payload)
        filename_mime_dict = stage_documents_from_manifest(stage_dir, args.rawFilesystemMount, payload)
        validate_documents(scanner, args.scannerFileMount, stage_dir, filename_mime_dict)
        tx_id = write_metadata(connection, args.bucket, payload)
        write_to_obj_store(minio, args.bucket, payload)
        connection.commit()
        return jsonify({'status': 'ok', 'ref': tx_id}), {'Content-Type': 'application/json'}
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        if os.path.isdir(stage_dir):
            shutil.rmtree(stage_dir)
        if connection.is_connected():
            connection.close()

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/form/document', methods=['POST'])
@accept('text/html')
def submit_new_tx_form():
    stage_dir = stage_dirname(args.untrustedFilesystemMount)
    connection = connection_pool.get_connection()
    try:
        payload = get_payload_from_form(request)
        logging.info("Received FORM ingestion request: {}/{}".format(payload['realm'], payload['txId']))
        validate_manifest(payload)
        preprocess_manifest(payload)
        os.makedirs(stage_dir)
        filename_mime_dict = stage_documents_from_form(request, stage_dir, payload)
        validate_documents(scanner, args.scannerFileMount, stage_dir, filename_mime_dict)
        tx_id = write_metadata(connection, args.bucket, payload)
        write_to_obj_store(minio, args.bucket, payload)
        connection.commit()
        return "txId: {}".format(tx_id), 'text/html'
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        if os.path.isdir(stage_dir):
            shutil.rmtree(stage_dir)
        if connection.is_connected():
            connection.close()

@app.route('/health', methods=['GET'])
def get_health():
    db_healthy = db_healthcheck()
    minio_healthy = minio.bucket_exists(args.bucket)
    scanner_healthy = scanner.ping() == "PONG"
    healthy_overall = db_healthy and minio_healthy and scanner_healthy
    return jsonify({'system': health_status(healthy_overall), 
                'db': health_status(db_healthy), 
                'minio': health_status(minio_healthy), 
                'scanner': health_status(scanner_healthy)})

@app.errorhandler(ValidationException)
def handle_validation_error(e):
    return str(e), 400

@app.errorhandler(Exception)
def handle_internal_error(e):
    logging.error(e, exc_info=True)
    return str(e), 500

if __name__ == '__main__':
    parse_args()
    logging.getLogger().setLevel(args.log)
    init_db()
    init_obj_store()
    init_virus_scanner()

    app.run(debug=args.debug)

