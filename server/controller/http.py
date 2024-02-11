from flask import Flask, jsonify, request, send_from_directory
from flask_accept import accept
from flask_cors import CORS
import logging
import os
import shutil
import uuid

from exceptions import ValidationException
from model.submit_service import validate_manifest, preprocess_manifest, write_metadata, stage_documents_from_manifest, validate_documents, stage_documents_from_form, get_payload_from_form, write_to_obj_store

app = Flask('docriver-http-gateway')
CORS(app, resources={r"/*": {"origins": "*"}})

def stage_dirname(untrusted_file_mount):
    return "{}/{}".format(untrusted_file_mount, uuid.uuid1())
    
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

def receive_requests(_args, _connection_pool, _minio, _scanner):
    global args
    global minio
    global connection_pool
    global scanner

    args = _args
    minio = _minio
    connection_pool = _connection_pool
    scanner = _scanner
    app.run(debug=args.debug)
