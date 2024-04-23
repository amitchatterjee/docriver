from flask import Flask, Blueprint, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_accept import accept
import logging
import os

from exceptions import ValidationException, AuthorizationException, DocumentException
from model.tx_submit_service import submit_docs_tx
from model.tx_delete_service import delete_docs_tx
from actuator.health import get_health
from controller.html_utils import to_html
from model.document_service import stream_document

gw = Blueprint('docriver-http', __name__)

@gw.route('/tx/<realm>', methods=['POST'])
def process_submit_tx(realm):
    result = submit_docs_tx(untrusted_fs_mount, raw_fs_mount, scanner_fs_mount, bucket, connection_pool, minio, scanner, auth_public_keys, auth_audience, realm, request)
    if request.headers.get('Accept', default='text/html') == 'application/json':
        return jsonify(result), {'Content-Type': 'application/json'}
    else:
        # TODO use a jinja template
        # return '<pre>{}</pre>'.format(pprint.pformat(result)), 'text/html'
        return to_html(result, indent=1), 200, {'Content-Type': 'text/html'}

@gw.route('/tx/<realm>', methods=['DELETE'])
@accept('application/json')
def process_delete_tx(realm):
    payload = request.json
    token = payload['authorization'] if 'authorization' in payload else request.headers.get('Authorization')
    result = delete_docs_tx(token, realm, payload, connection_pool, auth_public_keys, auth_audience)
    return jsonify(result), {'Content-Type': 'application/json'}

@gw.route('/document/<realm>/<path:document>', methods=['GET'])
def process_document_get(realm, document):
    token = request.args.get('authorization') if request.args.get('authorization') else request.headers.get('Authorization')
    return stream_document(connection_pool, minio, bucket, realm, document, auth_public_keys, auth_audience, token)

@gw.route('/favicon.ico')
def favicon():
    # TODO - change this to a redirect URL to a server that handles static content
    return send_from_directory(os.path.join(gw.root_path, 'resources/image'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')
@gw.route('/js/<path:script>')
def javascript(script):
    # TODO - change this to a redirect URL to a server that handles static content
    return send_from_directory(os.path.join(gw.root_path, 'resources/js'),
                               script, mimetype='text/javascript')

@gw.route('/css/<path:stylesheet>')
def css(stylesheet):
    # TODO - change this to a redirect URL to a server that handles static content
    return send_from_directory(os.path.join(gw.root_path, 'resources/css'),
                               stylesheet, mimetype='text/css')

@gw.route('/health', methods=['GET'])
def health_status():
    return jsonify(get_health(bucket, connection_pool, minio, scanner))

@gw.errorhandler(ValidationException)
def handle_validation_error(e):
    return str(e), 400

@gw.errorhandler(DocumentException)
def handle_document_error(e):
    return str(e), 404

@gw.errorhandler(AuthorizationException)
def handle_authorization_error(e):
    return str(e), 401

@gw.errorhandler(Exception)
def handle_internal_error(e):
    logging.error(e, exc_info=True)
    return str(e), 500

def init_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.register_blueprint(gw)
    return app

def init_params(_connection_pool, _minio, _scanner, _bucket, _untrusted_fs_mount, _raw_fs_mount, _scanner_fs_mount, _auth_private_key, _auth_public_key, _auth_signer_cert, _auth_signer_cn, _auth_public_keys, _auth_audience):
    # TODO this is getting ugly fast. Fixit
    global minio
    global connection_pool
    global scanner
    global bucket
    global untrusted_fs_mount
    global raw_fs_mount
    global scanner_fs_mount
    global auth_private_key
    global auth_public_key
    global auth_signer_cert
    global auth_signer_cn
    global auth_public_keys
    global auth_audience

    minio = _minio
    connection_pool = _connection_pool
    scanner = _scanner
    bucket = _bucket
    untrusted_fs_mount = _untrusted_fs_mount
    raw_fs_mount = _raw_fs_mount
    scanner_fs_mount = _scanner_fs_mount
    auth_private_key = _auth_private_key
    auth_public_key = _auth_public_key
    auth_signer_cert = _auth_signer_cert
    auth_signer_cn = _auth_signer_cn
    auth_public_keys = _auth_public_keys
    auth_audience = _auth_audience