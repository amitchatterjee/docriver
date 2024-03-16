from auth.token import decode
from exceptions import AuthorizationException
import re
import logging

def raiseif(cond, msg):
    if cond:
        raise AuthorizationException(msg)

def authorize_submit(public_keys, token, audience, payload):
    auth = None 
    issuer = None
    if not public_keys:
        payload['dr:principal'] = 'unknown'
        return auth, issuer
    try:
        raiseif (not token, "Token not specified")
        splits = re.split('\s+', token)
        raiseif (len(splits) != 2, "Invalid token format")
        
        raiseif (splits[0].upper() != 'BEARER', "Invalid token type {}".format(token))

        auth, issuer = decode(public_keys, splits[1], audience)
        raiseif(issuer != payload['realm'] and issuer != 'docriver', 'Invalid issuer')
        raiseif('permissions' not in auth, 'No permissions available')

        raiseif('realm' not in auth['permissions'], 'Realm not specified')
        raiseif(not re.match(auth['permissions']['realm'], payload['realm']), "Realm does not match")

        # TODO check if we can avoid the int coversion below
        document_count =  int(auth['permissions']['documentCount']) if 'documentCount' in auth['permissions'] else 1
        raiseif (len(payload['documents']) > document_count, "Document count exceeds allowed")

        for document in payload['documents']:
            all_references = payload['references'] if 'references' in payload else [] \
                + document['references'] if 'references' in document else []
            raiseif(len(all_references) == 0 and 'resourceType' in auth, 'References are required')
            for reference in all_references:
                authorize_reference(auth, reference)

        logging.getLogger('Authorization').info("Authorized transaction: {} - realm: {} subject: {}, issuer: {}".format(payload['tx'], payload['realm'], auth['sub'], issuer))

        payload['dr:principal'] = auth['sub']
        return auth, issuer
    except Exception as e:
        logging.getLogger('Authorization').warning("Authorization failure - issuer: {}, token: {}, exception: {}".format(issuer, auth, e))
        raise AuthorizationException('Not authorized for this operation') from e

def authorize_reference(auth, reference):
    if 'resourceType' in auth:
        # Resource type validation is needed
        raiseif(not re.match(auth['permissions']['resourceType'], reference['resourceType']), "resourceType does not match")
    if 'resourceId' in auth['permissions']:
        # Resource ID validation is needed
        raiseif(not re.match(auth['permissions']['resourceId'], reference['resourceId']), "resourceId does not match")
