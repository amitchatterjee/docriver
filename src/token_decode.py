#!/usr/bin/env python

import argparse
from pprint import pprint
from auth.keystore import get_entries
from auth.token import decode

def parse_args():
    parser = argparse.ArgumentParser(description='Authorize JWT token')
    parser.add_argument('--keystore', default='docriver.p12',
                        help='A PKCS12 keystore file')
    parser.add_argument('--password', default=None,
                        help='Keystore password')
    parser.add_argument('--audience', default='docriver',
                        help='Target application')
    parser.add_argument('--token', required=True,
                        help='The bearer token')    
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(args.keystore, args.password)
    decoded = decode(public_keys, args.token, args.audience)

    # Print logs
    print("Successfully authorized bearer token")
    pprint(decoded)

