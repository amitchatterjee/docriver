import argparse
import logging
import os
import sys
import base64
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_accept import accept

from exceptions import ValidationException, AuthorizationException
from auth.keystore import get_entries
from auth.token import issue

app = Flask(__name__)

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--httpPort", type=int, help="HTTP port number", default=5001)

    parser.add_argument('--keystore', default=os.path.join(os.getenv('HOME'), '.ssh/docriver.p12'),
                        help='A PKCS12 keystore file')
    parser.add_argument('--password', default=None,
                        help='Keystore password')
    parser.add_argument("--log", help="log level (valid values are INFO, WARNING, ERROR, NONE", default='WARN')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args(args)
    # TODO add validation
    return args

@app.route('/token', methods=['POST'])
def get_token():
    payload = request.json

    authorization = payload['authorization'] if 'authorization' in payload else request.headers.get('Authorization', default=None)

    if 'audience' not in payload:
        raise ValidationException('audience is required')
    audience = payload['audience']

    if 'permissions' not in payload:
        raise ValidationException('permissions is required')
    permissions = payload['permissions']
    
    splits = authorization.split()
    if splits[0].lower() != 'basic':
        raise ValidationException('Only basic authentication is supported')
    
    user_passwd = str(base64.b64decode(bytes(splits[1], 'utf-8')))
    splits = user_passwd.split(':')

    passwd = splits[1]
    subject = splits[0]

    # TODO validate the authorization and override parameters, as needed
    
    permissions['tx'] = str(uuid.uuid4())

    # TODO pass it as command line param instead of hardcoding    
    expires = 60

    resource = payload['resource'] if 'resource' in payload else 'document'

    encoded, payload = issue(private_key, signer_cn, subject, audience, expires, resource, permissions)

    # TODO fix this
    logging.info("Token issued to {}".format(subject))
    return jsonify({'authorization': 'Bearer ' + encoded, 'token': payload}), 200, {'Content-Type': 'application/json'}

@app.errorhandler(ValidationException)
def handle_validation_error(e):
    return jsonify({'error': str(e)}), 400, {'Content-Type': 'application/json'}

@app.errorhandler(AuthorizationException)
def handle_validation_error(e):
    logging.warn("Authorization exception {}".format(str(e)))
    return jsonify({'error': 'Authorizaton failed'}), 404, {'Content-Type': 'application/json'}

@app.errorhandler(Exception)
def handle_internal_error(e):
    logging.error(e, exc_info=True)
    return jsonify({'error': str(e)}), 500, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    global private_key, signer_cn, signer_cert
    args = parse_args(sys.argv[1:])
    logging.basicConfig(level=args.log)

    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(args.keystore, args.password)
    
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.run(host="0.0.0.0", port=args.httpPort, debug=args.debug)