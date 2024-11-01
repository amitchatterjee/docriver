#!/usr/bin/env python

import argparse
import os
from pprint import pprint
from docriver_auth.keystore import get_entries
from docriver_auth.auth_token import issue

def parse_args():
    parser = argparse.ArgumentParser(description='Issue JWT token')
    parser.add_argument('--keystore', default=os.path.join(os.getenv('HOME'), '.ssh/docriver.p12'),
                        help='A PKCS12 keystore file')
    parser.add_argument('--password', default=None,
                        help='Keystore password')
    parser.add_argument('--audience', default='docriver',
                        help='Target application')
    parser.add_argument('--resource', required=True,
                        help='resource to authorize')
    parser.add_argument('--subject', default='anon',
                        help='Principal of the subject')
    parser.add_argument('--expires', default=60, type=int,
                        help='Expires after EXPIRES')
    parser.add_argument('--permissions', metavar='KEY[:VALUE]', nargs='+', default=[],
                        help='Permissions associated with this subject')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()    

if __name__ == '__main__':
    args = parse_args()
    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(args.keystore, args.password)
    encoded,payload = issue(private_key, signer_cn, args.subject, args.audience, args.expires,  args.resource, args.permissions)
    if args.debug:
        print('The following payload will be encoded:')
        pprint(payload)
        print('------Copy and paste the code after this line------')
        print(encoded)
        print('------Copy and paste the code before this line------')
    else:
        print(encoded)
