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

from exceptions import ValidationException, AuthorizationException
from auth.keystore import get_entries
from auth.token import issue
from okta.verify import OktaTokenValidator

app = Flask(__name__)

# TODO read from files
allowed_operations = {
    'appealsSupport': ['get-document', 'submit', 'delete'],
    'appealsAuditor': ['get-document']
}

allowed_resources = {
    'appealsSupport': ['claim']
}

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
        
        authorize_element(assigned, requested_permissions, allowed_operations, 'txType')

        if requested_permissions['txType'] == 'submit':
            authorize_element(assigned, requested_permissions, allowed_resources, 'resourceType')

    except(json.decoder.JSONDecodeError):
        raise ValidationException("Assigned permissions not in JSON format")


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
    logging.warn("Authorization exception: {}".format(str(e)))
    return jsonify({'error': 'Authorizaton failed'}), 403, {'Content-Type': 'application/json'}

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