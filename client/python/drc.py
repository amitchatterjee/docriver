#!/usr/bin/env python

import argparse
import os
import logging
import sys
import requests
import traceback
import json
import re
import uuid
import time
import tempfile
import mimetypes
from urllib.parse import quote
import urllib3

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.requests import RequestsInstrumentor

sys.path.append(os.path.abspath(os.path.join(
    os.getenv('DOCRIVER_GW_HOME'), 'server')))

from auth.token import issue
from auth.keystore import get_entries

tracer = None

def parse_toplevel_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--docriverUrl", help="Document gateway URL", default='http://localhost:5000')
    parser.add_argument('--keystore', default=os.path.join(os.getenv('HOME'), '.ssh/docriver.p12'),
                        help='A PKCS12 keystore file')
    parser.add_argument('--keystorePassword', default=None,
                        help='Keystore password')
    parser.add_argument('--subject', default='anon',
                        help='Principal of the subject')
    parser.add_argument('--audience', default='docriver',
                        help='Target application')
    parser.add_argument('--resource', default='document',
                        help='resource to authorize')
    parser.add_argument("--realm", required=True,
                        help="Realm to submit document to")
    parser.add_argument('--noverify', action='store_true')
    parser.add_argument(
        "--log", help="log level (valid values are DEBUG, INFO, WARN, ERROR, NONE", default='WARN')
    parser.add_argument('--debug', action='store_true')

    parser.add_argument(
        "--otelExp", help="Opentelemetry exporter. Valid values are: none, console and otlp", default=None)
    parser.add_argument(
        "--otelExpEndpoint", help="Opentelemetry exporter endpoint. Only required for OTLP exporter", default=None)

    parser.add_argument(
        "--otelAuthTokenKey", help="Opentelemetry auth token key name", default='auth')
    parser.add_argument("--otelAuthTokenVal",
                        help="Opentelemetry auth token value", default='')

    supported_commands = ['get', 'submit']
    parser.add_argument('command', type=str, choices=supported_commands,
                        help=f"operation verb. Valid values are: {supported_commands}")
    parser.add_argument('args', nargs=argparse.REMAINDER)

    return parser.parse_args()


def parse_get_args(global_args):
    parser = argparse.ArgumentParser()
    supported_resources = ['events', 'document']
    parser.add_argument(
        'command', help=f"resource to get. Supported resources: {supported_resources}")
    parser.add_argument('args', nargs=argparse.REMAINDER)
    return parser.parse_args(global_args.args)


def handle_get(global_args):
    args = parse_get_args(global_args)
    if args.command == 'events':
        handle_get_events(global_args, args)
    elif args.command == 'document':
        handle_get_doc(global_args, args)
    else:
        # Should not happen
        raise Exception('Unknown resource')


def handle_get_doc(global_args, args):
    args = parse_get_doc(args)
    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(
        global_args.keystore, global_args.keystorePassword)
    # TODO change to narrower permissions
    encoded, payload = issue(private_key, signer_cn, global_args.subject, global_args.audience,
                             60,  global_args.resource, {'txType': 'get-document', 'document': '.*'})

    with requests.get(f"{global_args.docriverUrl}/document/{global_args.realm}/{quote(args.name)}",
                      headers={'Authorization': f"Bearer {encoded}"}, verify=not global_args.noverify, stream=True) as response:
        response.raise_for_status()
        with open(args.output, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(json.dumps({'status': 'OK', 'path': args.output}, indent=2))


def parse_get_doc(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Output path", required=True)
    parser.add_argument("--name", help="Document name", required=True)
    args = parser.parse_args(args.args)
    return args


def parse_get_events(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fromTime", help="from time in Epoch seconds", type=int)
    parser.add_argument("--toTime", help="to time in Epoch seconds", type=int)
    args = parser.parse_args(args.args)
    return args


def handle_get_events(global_args, args):
    args = parse_get_events(args)
    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(
        global_args.keystore, global_args.keystorePassword)
    # TODO change to narrower permissions
    encoded, payload = issue(private_key, signer_cn, global_args.subject,
                             global_args.audience, 60,  global_args.resource, {'txType': 'get-events'})

    params = {}
    if args.fromTime:
        params['from'] = args.fromTime
    if args.toTime:
        params['to'] = args.toTime
    with requests.get(f"{global_args.docriverUrl}/tx/{global_args.realm}", params=params, headers={'Accept': 'application/json', 'Authorization': f"Bearer {encoded}"}, verify=not global_args.noverify) as response:
        response.raise_for_status()
        json_response = response.json()
        print(json.dumps(json_response, indent=2))


def parse_submit_args(global_args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", help="Full path name of the source location. Maybe a file or a directory", required=True)
    parser.add_argument("--rawFilesystemMount", help="mount point of the shared filesystem where raw documents is stored by applications. The applications can copy files to this location and specify the location instead of uploading")
    supported_methods = ['inline', 'upload', 'copy']
    parser.add_argument("--method", choices=supported_methods,
                        default='upload', help="Method by which the files are submitted")
    parser.add_argument("--prefix", default='',
                        help="Prefix used while naming the document(s)")
    parser.add_argument("--filter", default='.*',
                        help="Regex to filter filenames if the source is a directory")
    parser.add_argument("--documentType", help="The type of the document")
    parser.add_argument("--resourceType",
                        help="The type of resource for which these documents are being submiited")
    parser.add_argument("--resourceId",
                        help="Resource identifier for which these documents are being submiited")
    parser.add_argument("--resourceDescription",
                        help="Description of the purpose of this document")
    parser.add_argument("--replacesDocument",
                        help="The ID of the document that this document replaces")
    return parser.parse_args(global_args.args)


def handle_submit(global_args):
    files = []
    info = []
    args = parse_submit_args(global_args)
    if not os.path.exists(args.source):
        raise Exception("Source path does not exist")
    basedir = None
    if os.path.isdir(args.source):
        basedir = args.source
        files = [f for f in os.listdir(basedir) if not os.path.isdir(
            os.path.join(basedir, f)) and re.match(args.filter, f)]
    else:
        basedir, file = os.path.split(args.source)
        files.append(file)
        
    # TODO validate args
    raiseif(args.resourceId and not args.resourceType, 'If resourceId is specified, resourceType must also be specified')
    raiseif(len(files) > 1 and args.replacesDocument, "replacesDocument option is only supported when submitting a single document")

    # Create a manifest and save to a temporary location
    manifest = {'tx': f"{str(uuid.uuid4())}", 'documents': []}
    if args.resourceId:
        references = [{'resourceId': args.resourceId}]
        references[0]['resourceType'] = args.resourceType
        if args.resourceDescription:
            references[0]['resourceDescription'] = args.resourceDescription
        manifest['references'] = references

    manifest_path = None
    for file in files:
        index = file.rfind('.')
        # fname = file[:index]
        ext = file[index+1:]
        manifest['documents'].append({'document': f"{args.prefix}{file}-{int(time.time())}",
                                     'type': args.documentType if args.documentType else ext,
                                      'content': {'path': file},
                                      'properties': {'filename': file}})

    with tempfile.NamedTemporaryFile(mode='w+t', delete=False, suffix='.json', prefix='manifest-') as tmpfile:
        tmpfile.write(json.dumps(manifest))
        manifest_path = tmpfile.name
    info.append({'manifest': manifest_path})

    # Setup auth token
    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(
        global_args.keystore, global_args.keystorePassword)
    requested_grants = {'txType': 'submit', 'documentCount': len(files)}
    if args.resourceId:
        requested_grants['resourceId'] = args.resourceId
        requested_grants['resourceType'] = args.resourceType
    encoded, payload = issue(private_key, signer_cn, global_args.subject,
                             global_args.audience, 60,  global_args.resource, requested_grants)

    # Create form data upload list
    form_files = [('files', ('manifest.json', open(
        manifest_path, 'r'), 'application/json'))]
    for file in files:
        mime = mimetypes.guess_type(file)[0]
        form_files.append(
            ('files', (file, open(os.path.join(basedir, file), 'rb'), mime)))

    # Send the request
    with requests.post(f"{global_args.docriverUrl}/tx/{global_args.realm}",
                       headers={'Authorization': f"Bearer {encoded}", 'Accept': 'application/json'}, verify=not global_args.noverify, files=form_files) as response:
        response.raise_for_status()
        response_json = response.json()
        response_json['info'] = info
        print(json.dumps(response_json, indent=2))

def handle_command(args):
    if args.command == 'get':
        handle_get(args)
    elif args.command == 'submit':
        handle_submit(args)


def init_tracer(exp=None, endpoint=None, auth_token_key=None, auth_token_val=None):
    resources = {'service.name': 'docriver-client', 'service.version': '1.0.0',
                 'deployment.environment': 'development'}
    if auth_token_key:
        resources[auth_token_key] = auth_token_val

    resource = Resource.create(resources)

    provider = TracerProvider(resource=resource)
    if exp == 'console':
        processor = SimpleSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
    elif exp == 'otlp':
        processor = SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        provider.add_span_processor(processor)
    else:
        logging.getLogger('Tracer').warning("Tracer disabled!!!")

    # Sets the global default tracer provider
    trace.set_tracer_provider(tracer_provider=provider)

    # Creates a tracer from the global tracer provider
    tracer = trace.get_tracer("docriver-client")
    RequestsInstrumentor().instrument()
    return tracer

def raiseif(cond, msg):
    if cond:
        raise Exception(msg)
    
if __name__ == '__main__':
    args = None
    try:
        args = parse_toplevel_args()
        # print(args)
        logging.basicConfig(level=args.log)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        tracer = init_tracer(args.otelExp, args.otelExpEndpoint,
                             args.otelAuthTokenKey, args.otelAuthTokenVal)
        handle_command(args)
    except Exception as e:
        if args and args.debug:
            print(traceback.format_exc(), file=sys.stderr)
        else:
            print(e, file=sys.stderr)
        sys.exit(1)
