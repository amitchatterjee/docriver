import pprint
from flask import Flask, jsonify, request, send_from_directory
from flask_accept import accept
from flask_cors import CORS
import logging
import os
import uuid
import time

from exceptions import ValidationException
from model.tx_submit_service import new_tx
from controller.html_utils import to_html

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

@app.route('/tx', methods=['POST'])
def process_new_tx():
    result = new_tx(args.untrustedFilesystemMount, args.rawFilesystemMount, args.scannerFileMount, args.bucket, connection_pool, minio, scanner, request)
    if request.headers.get('Accept', default='text/html') == 'application/json':
        return jsonify(result), {'Content-Type': 'application/json'}
    else:
        # TODO use a jinja template
        # return '<pre>{}</pre>'.format(pprint.pformat(result)), 'text/html'
        return to_html(result, indent=1), 'text/html'

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

def process_requests(_args, _connection_pool, _minio, _scanner):
    global args
    global minio
    global connection_pool
    global scanner

    args = _args
    minio = _minio
    connection_pool = _connection_pool
    scanner = _scanner
    app.run(debug=args.debug)
