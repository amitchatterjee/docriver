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
from okta.verify import OktaTokenValidator

app = Flask(__name__)

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--httpPort", type=int, help="HTTP port number", default=5001)

    parser.add_argument('--keystore', default=os.path.join(os.getenv('HOME'), '.ssh/docriver.p12'),
                        help='A PKCS12 keystore file')
    parser.add_argument('--password', default=None,
                        help='Keystore password')
    
    parser.add_argument('--oktaUrl', default=None,
                        help='OKTA token URL')
    parser.add_argument('--oktaAud', default=None,
                        help='OKTA token audience')
    
    parser.add_argument("--log", help="log level (valid values are INFO, WARNING, ERROR, NONE", default='WARN')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args(args)
    # TODO add validation
    return args

@app.route('/token', methods=['POST'])
def get_token():
    payload = request.json

    subject = None
    assigned_permissions = None
    authorization = payload['authorization'] if 'authorization' in payload else request.headers.get('Authorization') if 'Authorization' in request.headers else request.cookies['auth'] if 'auth' in request.cookies else None
    if authorization:
        splits = authorization.split()
        if splits[0].lower() == 'basic':
            user_passwd = str(base64.b64decode(bytes(splits[1], 'utf-8')))
            splits = user_passwd.split(':')
            passwd = splits[1]
            subject = splits[0]
            assigned_permissions = None
            # TODO Authenticate the user and get the permissions from the user profile
        elif splits[0].lower() == 'bearer':
            subject,assigned_permissions = extract_subject_and_permissions(splits[1])
        else:
            raise ValidationException('Unsupported authorization method')
    else:
        raise ValidationException('Authorization not found')

    if 'audience' not in payload:
        raise ValidationException('audience is required')
    audience = payload['audience']

    if 'permissions' not in payload:
        raise ValidationException('permissions is required')
    permissions = payload['permissions']

    # TODO validate the permissions assigned to the user against the requested permissions

    permissions['tx'] = str(uuid.uuid4())

    # TODO pass it as command line param instead of hardcoding    
    expires = 60

    resource = payload['resource'] if 'resource' in payload else 'document'

    encoded, payload = issue(private_key, signer_cn, subject, audience, expires, resource, permissions)

    # TODO fix this
    logging.info("Token issued to {}".format(subject))
    return jsonify({'authorization': 'Bearer ' + encoded, 'token': payload}), 200, {'Content-Type': 'application/json'}

def extract_subject_and_permissions(token):
    headers, claims, signing_inputs, signature = okta_token_validator.verify(token)
    subject = claims['sub']
    permissions = claims['docriverPermissions'] if 'docriverPermissions' in claims else None
    return subject,permissions

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
    global private_key, signer_cn, signer_cert, okta_token_validator
    args = parse_args(sys.argv[1:])
    logging.basicConfig(level=args.log)

    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(args.keystore, args.password)
    
    okta_token_validator = None
    if args.oktaUrl:
        okta_token_validator = OktaTokenValidator(args.oktaUrl, args.oktaAud)

    CORS(app, resources={r"/*": {"origins": "*"}})
    app.run(host="0.0.0.0", port=args.httpPort, debug=args.debug)