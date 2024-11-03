import argparse
import logging
import os
import sys
import base64
import uuid
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_accept import accept
from okta.verify import OktaTokenValidator

from exceptions import AuthorizationException
from keystore import get_entries
from auth_token import issue

app = Flask(__name__)

class ValidationException(Exception):
    def __init__(self, message="Validation exception"):
        self.message = message
        super().__init__(self.message)

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
    
    parser.add_argument('--permissions', required=True,
                        help="A file containing all the grants/permissions for various roles")
    
    parser.add_argument('--tlsKey', default=None,
                        help="A file containing the site's TLS private key (PEM)")
    parser.add_argument('--tlsCert', default=None,
                        help="A file containing the site's TLS certificate (PEM)")

    parser.add_argument("--log", help="log level (valid values are INFO, WARNING, ERROR, NONE", default='WARNING')
    parser.add_argument('--debug', action='store_true')

    args = parser.parse_args(args)
    # TODO add validation
    return args

def authorize_element(assigned_permissions, requested_permissions, table, attribute):
    assigned_roles = assigned_permissions["roles"]
    for assigned_role in assigned_roles:
        if assigned_role in table:
            values = table[assigned_role]
        if requested_permissions[attribute] in values:
            return
        
    raise AuthorizationException("Unauthorized attribute {}/{}".format(attribute, requested_permissions[attribute]))

def authorize_request(assigned_permissions, requested_permissions):
    if not assigned_permissions:
        raise AuthorizationException("Not authorized for this application")
    
    try:
        assigned = json.loads(assigned_permissions)

        if 'realms' not in assigned:
            raise ValidationException("Realms not specified in the assigned permission")
        
        if 'roles' not in assigned:
            raise ValidationException("Roles not specified in the assigned permission")
        
        if 'resources' not in assigned:
            raise ValidationException("Resources not specified in the assigned permission")

        if 'realm' in requested_permissions:
            # Check if the requested realm is in the assigned realm
            if not next((e for e in assigned['realms'] if e in requested_permissions['realm']), None):
                raise AuthorizationException("Realm unathorized")
        else:
            # Create a regex with all the assigned realms
            requested_permissions['realm'] = "({})".format('|'.join(assigned['realms']))
        
        authorize_element(assigned, requested_permissions, permissions['operations'], 'txType')

        if requested_permissions['txType'] == 'submit':
            authorize_element(assigned, requested_permissions, permissions['resources'], 'resourceType')

    except(json.decoder.JSONDecodeError):
        raise ValidationException("Assigned permissions not in JSON format")


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'system': 'UP'}), 200, {'Content-Type': 'application/json'}

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
            # TODO Authenticate the user and get the permissions from the user profile
            assigned_permissions = None
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
    requested_permissions = payload['permissions']

    # Validate the permissions assigned to the user against the requested permissions
    authorize_request(assigned_permissions,requested_permissions)

    requested_permissions['tx'] = str(uuid.uuid4())

    # TODO pass it as command line param instead of hardcoding    
    expires = 60

    resource = payload['resource'] if 'resource' in payload else 'document'

    encoded, payload = issue(private_key, signer_cn, subject, audience, expires, resource, requested_permissions)

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
    logging.warning("Authorization exception: {}".format(str(e)))
    return jsonify({'error': 'Authorizaton failed'}), 403, {'Content-Type': 'application/json'}

@app.errorhandler(Exception)
def handle_internal_error(e):
    logging.error(e, exc_info=True)
    return jsonify({'error': str(e)}), 500, {'Content-Type': 'application/json'}

if __name__ == '__main__':
    global private_key, signer_cn, signer_cert, okta_token_validator, permissions
    
    args = parse_args(sys.argv[1:])
    logging.basicConfig(level=args.log)

    file_content = None
    with open(args.permissions, 'r') as file:
        file_content = file.read()
    permissions = json.loads(file_content)

    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(args.keystore, args.password)
    
    okta_token_validator = None
    if args.oktaUrl:
        okta_token_validator = OktaTokenValidator(args.oktaUrl, args.oktaAud)

    CORS(app, resources={r"/*": {"origins": "*"}})
    
    if args.tlsKey:
        logging.info("Starting server in TLS mode - cert: {}, key: {}".format(args.tlsCert, args.tlsKey))
        app.run(host="0.0.0.0", ssl_context=(args.tlsCert, args.tlsKey), port=args.httpPort, debug=args.debug)
    else:
        logging.warning("Starting server in non-TLS mode")
        app.run(host="0.0.0.0", port=args.httpPort, debug=args.debug)
