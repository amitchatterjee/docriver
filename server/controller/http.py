import pprint
from flask import Flask, jsonify, request, send_from_directory
from flask_accept import accept
from flask_cors import CORS
import logging
import os
import shutil
import uuid
import time

from exceptions import ValidationException
from model.submit_service import validate_manifest, preprocess_manifest, write_metadata, stage_documents_from_manifest, validate_documents, stage_documents_from_form, get_payload_from_form, write_to_obj_store

app = Flask(__name__)
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

def format_html(obj, indent = 1):
    if isinstance(obj, list):
        htmls = []
        for k in obj:
            htmls.append(format_html(k,indent+1))
        return '[<div style="margin-left: %dem">%s</div>]' % (indent, ',<br>'.join(htmls))

    if isinstance(obj, dict):
        htmls = []
        for k,v in obj.items():
            htmls.append("<span style='font-style: italic; color: #888'>%s</span>: %s" % (k,format_html(v,indent+1)))
        return '{<div style="margin-left: %dem">%s</div>}' % (indent, ',<br>'.join(htmls))
    return str(obj)

@app.route('/tx', methods=['POST'])
def submit_docs():
    start = int(round(time.time() * 1000))
    rest = request.content_type == 'application/json'
    payload = None
    stage_dir = stage_dirname(args.untrustedFilesystemMount)
    connection = connection_pool.get_connection()
    try:
        if rest:
            payload = request.json
        else:
            # Assume multipart/form or multipart/mixed
            payload = get_payload_from_form(request)

        validate_manifest(payload)

        os.makedirs(stage_dir)
        logging.info("Received submission request: {}/{}. Content-Type: {}, Accept: {}".format(payload['realm'], payload['tx'], request.content_type, request.headers.get('Accept', default='text/html')))

        preprocess_manifest(payload)

        filename_mime_dict = None
        if rest:
            filename_mime_dict = stage_documents_from_manifest(stage_dir, args.rawFilesystemMount, payload)
        else:
            filename_mime_dict = stage_documents_from_form(request, stage_dir, payload)

        validate_documents(scanner, args.scannerFileMount, stage_dir, filename_mime_dict)
        write_metadata(connection, args.bucket, payload)
        write_to_obj_store(minio, args.bucket, payload)
        connection.commit()

        end = int(round(time.time() * 1000))
        result = format_result(start, payload, end)
        
        if request.headers.get('Accept', default='text/html') == 'application/json':
            return jsonify(result), {'Content-Type': 'application/json'}
        else:
            # TODO use a jinja template
            # return '<pre>{}</pre>'.format(pprint.pformat(result)), 'text/html'
            return format_html(result, indent=1), 'text/html'
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        if os.path.isdir(stage_dir):
            shutil.rmtree(stage_dir)
        if connection.is_connected():
            connection.close()

def format_result(start, payload, end):
    result = {'dr:status': 'ok', 'dr:took': end - start}
    for document in payload['documents']:
        del document['dr:stageFilename']
        if 'content' in document and 'inline' in document['content']:
            document['content']['inline'] = '<snipped>'
    result.update(payload)
    return result

@app.route('/favicon.ico')
def favicon():
    # TODO - change this to a redirect URL to a server that handles static content
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

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
