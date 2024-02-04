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

from exceptions import ValidationException
from document_ingest import validate_manifest, preprocess_manifest, ingest_tx, stage_documents, validate_documents

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def stage_dirname(untrusted_file_mount):
    return "{}/{}".format(untrusted_file_mount, uuid.uuid1())

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

def ingest(payload):
    stage_dir = stage_dirname(args.untrustedFileMount)
    try:
        os.makedirs(stage_dir, exist_ok=True)
        logging.info("Received REST ingestion request: {}/{}".format(payload['realm'], payload['txId']))
        validate_manifest(payload)
        preprocess_manifest(payload)
        stage_documents(stage_dir, args.rawFileMount, payload)
        validate_documents(stage_dir)
        return ingest_tx(cnx, minio, args.bucket, payload)
    finally:
        if os.path.isdir(stage_dir):
            shutil.rmtree(stage_dir)

@app.route('/rest/document', methods=['POST', 'PUT'])
@accept('application/json')
def ingest_json():
    tx_id = ingest(request.json)
    return jsonify({'status': 'ok', 'ref': tx_id}), {'Content-Type': 'application/json'}

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

def find_matching_document(documents, filename):
    for document in documents:
        if document['content']['filePath'] == '/' + filename:
            return document
    raise ValidationException('file not found')

@app.route('/form/document', methods=['POST'])
@accept('text/html')
def upload_file():
    manifest = request.form['manifest']
    payload = json.loads(manifest)
    logging.info("Received FORM ingestion request: {}/{}".format(payload['realm'], payload['txId']))

    validate_manifest(payload)
    preprocess_manifest(payload)
    stage_dir = stage_dirname(args.untrustedFileMount)
    
    try:
        os.makedirs(stage_dir)
        for uploaded_file in request.files.getlist('files'):
            staged_filename = "{}/{}".format(stage_dir, uploaded_file.filename)
            uploaded_file.save(staged_filename)
            document = find_matching_document(payload['documents'], uploaded_file.filename)['dr:stageFilename'] = staged_filename

        validate_documents(stage_dir)
        tx_id = ingest_tx(cnx, minio, args.bucket, payload)
        return "txId: {}".format(tx_id), 'text/html'
    finally:
         if os.path.isdir(stage_dir):
            shutil.rmtree(stage_dir)

# curl -H "Content-Type: multipart/mixed" -F "request={"param1": "value1"};type=application/json"

if __name__ == '__main__':
    parse_args()

    logging.getLogger().setLevel(args.log)

    init_db()
    init_obj_store()

    app.run(debug=True)

