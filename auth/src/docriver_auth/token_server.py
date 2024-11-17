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
from passlib.apache import HtpasswdFile
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
 
    parser.add_argument('--users', default=None,
                        help="A file containing all users/roles/etc. Used for basic authorization")
    parser.add_argument('--passwords', default=None,
                        help="A file containing htpasswords. Used for basic authentication")
    
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

def authorize_operation(assigned_permissions, operation):
    assigned_roles = assigned_permissions["roles"]
    for assigned_role in assigned_roles:
        if assigned_role in permissions and operation in permissions[assigned_role]:
            return
    raise AuthorizationException(f"Unauthorized operation: {operation}")

def authorize_resource(assigned_permissions, resource):
    if resource not in assigned_permissions["resources"]:
        raise AuthorizationException(f"Unauthorized resource: {resource}")

def authorize_request(assigned_permissions, requested_permissions):
    # logging.info(f"assigned: {assigned_permissions}\nrequested: {requested_permissions}")
    if 'realms' not in assigned_permissions:
        raise ValidationException("Realms not specified in the assigned permission")
    
    if 'roles' not in assigned_permissions:
        raise ValidationException("Roles not specified in the assigned permission")
    
    if 'resources' not in assigned_permissions:
        raise ValidationException("Resources not specified in the assigned permission")

    if 'realm' in requested_permissions:
        # Check if the requested realm is in the assigned realm
        if requested_permissions['realm'] not in assigned_permissions['realms']:
            raise AuthorizationException("Realm unathorized")
    else:
        # TODO - make realm mandatory instead of doing this - this is not very secure
        # Create a regex with all the assigned realms
        requested_permissions['realm'] = "({})".format('|'.join(assigned_permissions['realms']))
    
    authorize_operation(assigned_permissions, requested_permissions['txType'])

    if requested_permissions['txType'] == 'submit':
        authorize_resource(assigned_permissions, requested_permissions['resourceType'])

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
            subject,assigned_permissions = get_sub_and_perms_from_db(splits[1])
        elif splits[0].lower() == 'bearer':
            subject,assigned_permissions = get_sub_and_perms_from_token(splits[1])
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
    authorize_request(assigned_permissions, requested_permissions)

    # Assign a transaction id
    if 'tx' not in requested_permissions:
        requested_permissions['tx'] = str(uuid.uuid4())

    # TODO pass it as command line param instead of hardcoding    
    expires = 60

    resource = payload['resource'] if 'resource' in payload else 'document'

    encoded, payload = issue(private_key, signer_cn, subject, audience, expires, resource, requested_permissions)

    logging.info("Token issued to {}".format(subject))
    return jsonify({'authorization': 'Bearer ' + encoded, 'token': payload}), 200, {'Content-Type': 'application/json'}

def get_sub_and_perms_from_db(token):
    if not users:
        raise ValidationException('Basic Auth token validator is not configured')
    user_passwd = base64.b64decode(bytes(token, 'utf-8')).decode("utf-8")
    splits = user_passwd.split(':')
    subject = splits[0]
    passwd = splits[1]
    # Validate password
    if subject not in users:
        raise AuthorizationException(f"Authentication failed - user: {subject} not found")
    # TODO Introduce AuthenticationException
    if not passwords.check_password(subject, passwd):
        raise AuthorizationException("Authentication failed - password mismatch")
    assigned_permissions = users[subject]
    # logging.info(assigned_permissions)
    return subject,assigned_permissions

def get_sub_and_perms_from_token(token):
    if not okta_token_validator:
        raise ValidationException('Bearer token validator is not configured. Currently, only OKTA is supported for authorization tokens')
    headers, claims, signing_inputs, signature = okta_token_validator.verify(token)
    subject = claims['sub']
    permissions = claims['docriverPermissions'] if 'docriverPermissions' in claims else None
    
    if not permissions:
        raise AuthorizationException("Not authorized for this application")
    
    assigned_permissions = None
    try:
        assigned_permissions = json.loads(permissions)
        return subject,assigned_permissions
    except(json.decoder.JSONDecodeError):
        raise ValidationException("Assigned permissions not in JSON format")
    
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
    global private_key, signer_cn, signer_cert, okta_token_validator, permissions, users, passwords
    
    args = parse_args(sys.argv[1:])
    logging.basicConfig(level=args.log)

    file_content = None
    with open(args.permissions, 'r') as file:
        file_content = file.read()
    permissions = json.loads(file_content)

    if args.users:
        file_content = None
        with open(args.users, 'r') as file:
            file_content = file.read()
        users = json.loads(file_content)
        passwords = HtpasswdFile(args.passwords)
        
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
