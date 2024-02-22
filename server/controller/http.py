from flask import Flask, Blueprint, jsonify, request, send_from_directory
from flask_cors import CORS
import logging
import os

from exceptions import ValidationException
from model.tx_submit_service import new_tx
from actuator.health import get_health
from controller.html_utils import to_html

gw = Blueprint('docriver-http', __name__)

@gw.route('/tx', methods=['POST'])
def process_new_tx():
    result = new_tx(untrusted_fs_mount, raw_fs_mount, scanner_fs_mount, bucket, connection_pool, minio, scanner, request)
    if request.headers.get('Accept', default='text/html') == 'application/json':
        return jsonify(result), {'Content-Type': 'application/json'}
    else:
        # TODO use a jinja template
        # return '<pre>{}</pre>'.format(pprint.pformat(result)), 'text/html'
        return to_html(result, indent=1), 'text/html'

@gw.route('/favicon.ico')
def favicon():
    # TODO - change this to a redirect URL to a server that handles static content
    return send_from_directory(os.path.join(gw.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@gw.route('/health', methods=['GET'])
def health_status():
    return jsonify(get_health(bucket, connection_pool, minio, scanner))

@gw.errorhandler(ValidationException)
def handle_validation_error(e):
    return str(e), 400

@gw.errorhandler(Exception)
def handle_internal_error(e):
    logging.error(e, exc_info=True)
    return str(e), 500

def init_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.register_blueprint(gw)
    return app

def init_params(_connection_pool, _minio, _scanner, _bucket, _untrusted_fs_mount, _raw_fs_mount, _scanner_fs_mount):
    global minio
    global connection_pool
    global scanner
    global bucket
    global untrusted_fs_mount
    global raw_fs_mount
    global scanner_fs_mount

    minio = _minio
    connection_pool = _connection_pool
    scanner = _scanner
    bucket = _bucket
    untrusted_fs_mount = _untrusted_fs_mount
    raw_fs_mount = _raw_fs_mount
    scanner_fs_mount = _scanner_fs_mount