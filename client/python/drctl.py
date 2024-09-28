#!/usr/bin/env python

import argparse
import os
import logging
import sys
import requests

def parse_toplevel_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rawFilesystemMount", help="mount point of the shared filesystem where raw documents is stored by applications. The applications can copy files to this location and specify the location instead of uploading")
    parser.add_argument("--docriverUrl", help="Document gateway URL", default='http://localhost:5000')
    parser.add_argument('--keystore', default=os.path.join(os.getenv('HOME'), '.ssh/docriver.p12'),
                        help='A PKCS12 keystore file')
    parser.add_argument('--keystorePassword', default=None,
                        help='Keystore password')
    parser.add_argument('--subject', default='anon',
                        help='Principal of the subject')
    parser.add_argument('--audience', default='docriver',
                        help='Target application')
    parser.add_argument("--realm", required=True, help="Realm to submit document to")
    parser.add_argument('--noverify', action='store_true')
    parser.add_argument("--log", help="log level (valid values are DEBUG, INFO, WARN, ERROR, NONE", default='WARN')
    
    supported_commands=['get', 'submit']
    parser.add_argument('command', type=str, choices=supported_commands, help=f"operation verb. Valid values are: {supported_commands}")
    parser.add_argument('args', nargs=argparse.REMAINDER)
    
    return parser.parse_args()

def parse_get_args(global_args):
    parser = argparse.ArgumentParser()
    supported_resources=['events', 'document']
    parser.add_argument('command', help=f"resource to get. Supported resources: {supported_resources}")
    parser.add_argument('args', nargs=argparse.REMAINDER)
    return parser.parse_args(global_args.args)

def handle_get(global_args):
    args = parse_get_args(global_args)
    if args.command == 'events':
        handle_get_events(global_args, args)
    else:
        raise Exception('NYI')

def parse_get_events(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fromTime", help="from time in Epoch seconds", type=int)
    parser.add_argument("--toTime", help="to time in Epoch seconds", type=int)
    args = parser.parse_args(args.args)
    return args

def handle_get_events(global_args, args):
    args = parse_get_events(args)
    params = {}
    if args.fromTime:
        params['from'] = args.fromTime
    if args.toTime:
        params['to'] = args.toTime
    response = requests.get(f"{global_args.docriverUrl}/tx/{global_args.realm}", params=params, headers={'Accept': 'application/json'}, verify=not global_args.noverify)
    if response.status_code != 200:
        raise Exception(f"Response: {response.status_code}")
    print(response.text)

if __name__ == '__main__':
    try:
        args = parse_toplevel_args()
        #print(args)
        logging.basicConfig(level=args.log)
        
        if args.command == 'get':
            handle_get(args)
        else:
            raise Exception('NYI')
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)