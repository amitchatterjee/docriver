import datetime
import jwt

from docriver_auth.exceptions import AuthorizationException

def issue(private_key, signer_cn, subject, audience, expires, resource, permissions):
    ts = datetime.datetime.utcnow()
    perms = {}
    if isinstance(permissions, list):
        for permission in permissions:
            parts = permission.split(':')
            perms[parts[0]] = parts[1]
    else:
        # Assume dictionary
        perms = permissions

    payload = {
        'iss': signer_cn, 
        'aud': [audience],
        'iat': ts,
        'nbf': ts,
        'exp': ts + datetime.timedelta(seconds=expires),
        'sub': subject,
        'resource': resource,
        'permissions': perms
    }
    encoded = jwt.encode(payload, private_key, algorithm="RS256")
    return encoded,payload

def decode(public_keys, token, audience):
    # Read the payload without verification in order to get the issuer information
    payload = jwt.decode(token, options={"verify_signature": False})
    issuer = payload['iss']
    if issuer not in public_keys:
        raise AuthorizationException('Issuer not found')
    public_key = public_keys[issuer]

    # Verify signature to ensure that the issuer matches
    return jwt.decode(token, public_key, algorithms=["RS256"], audience=audience), issuer