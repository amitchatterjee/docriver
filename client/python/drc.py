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
import base64
import shutil
import paramiko

from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.trace import Status, StatusCode

sys.path.append(os.path.abspath(os.path.join(
    os.getenv('DOCRIVER_GW_HOME'), 'server')))

from auth.token import issue
from auth.keystore import get_entries

tracer = None

@contextmanager
def new_span(name, **kwargs):
    with tracer.start_as_current_span(name, **kwargs) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            raise e

def to_json(dict):
    return json.dumps(dict, indent=2)

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
        "--otelTraceExp", help="Opentelemetry exporter. Valid values are: none, console and otlp", default=None)
    parser.add_argument(
        "--otelTraceExpEndpoint", help="Opentelemetry exporter endpoint. Only required for OTLP exporter", default=None)

    parser.add_argument(
        "--otelTraceAuthTokenKey", help="Opentelemetry auth token key name", default='auth')
    parser.add_argument("--otelTraceAuthTokenVal",
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
    with new_span('get_doc', attributes={'realm': global_args.realm}) as span:
        args = parse_get_doc(args)
        private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(
            global_args.keystore, global_args.keystorePassword)
        # TODO change to narrower permissions
        encoded, payload = issue(private_key, signer_cn, global_args.subject, global_args.audience,
                                    60,  global_args.resource, {'txType': 'get-document', 'document': '.*'})

        with requests.get(f"{global_args.docriverUrl}/document/{global_args.realm}/{quote(args.name)}",
                            headers={'Authorization': f"Bearer {encoded}"}, verify=not global_args.noverify, stream=True) as response:
            response.raise_for_status()
            
            output_file = args.output
            if os.path.isdir(args.output):
                content_type = response.headers.get("Content-Type")
                extension = mimetypes.guess_extension(content_type)
                if not extension:
                    raise Exception("Cannot determine file extension. You must specify a full path name in the --output option")
                output_file = f"{args.output}/{str(uuid.uuid4())}{extension}"
                
            with open(output_file, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            print(to_json({'status': 'OK', 'path': output_file}))


def parse_get_doc(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Output path", default='/tmp')
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
    with new_span('get_events', attributes={'realm': global_args.realm}) as span:
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
            print(to_json(json_response))


def parse_submit_args(global_args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", help="Full path name of the source location. Maybe a file or a directory", required=True)
    supported_methods = ['inline', 'upload', 'copy', 'scp']
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
    parser.add_argument("--rawFilesystemMount", help="mount point of the shared filesystem where raw documents is stored by applications. The applications can copy files to this location and specify the location instead of uploading")
    parser.add_argument("--scpHost", default='locahost', help="Remote host name. The applications can upload the files using sftp/scp to this host and specify the location instead of uploading")
    parser.add_argument("--scpUser", help="Remote user name")
    parser.add_argument("--scpPassword", default='', help="Password for the user")
    parser.add_argument("--scpPath", default='./', help="Base path on the remote server where the file will be copied to")
    parser.add_argument('--autoAddHostKey', help="Auto-add host key", action=argparse.BooleanOptionalAction)
    
    return parser.parse_args(global_args.args)

def file_to_base64(file_path):
    with open(file_path, "rb") as file:
        file_content = file.read()
        base64_encoded = base64.b64encode(file_content)
        return base64_encoded.decode('utf-8')

def handle_submit(global_args):
    with new_span('submit', attributes={'realm': global_args.realm}) as span:
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
            
        # Validate args
        raiseif(args.resourceId and not args.resourceType, 'If resourceId is specified, resourceType must also be specified')
        raiseif(len(files) > 1 and args.replacesDocument, "replacesDocument option is only supported when submitting a single document")
        raiseif(args.method == 'copy' and not args.rawFilesystemMount, 'When the method is "copy", the rawFilesystemMount option must be specified')
        raiseif(args.method == 'scp' and not args.scpUser, 'When the method is "scp", the scpUser option must be specified')

        tx_id = f"{str(uuid.uuid4())}"
        span.set_attribute('tx', tx_id)
        # Create a manifest and save to a temporary location
        manifest = {'tx': tx_id, 'documents': []}
        if args.resourceId:
            references = [{'resourceId': args.resourceId}]
            references[0]['resourceType'] = args.resourceType
            if args.resourceDescription:
                references[0]['resourceDescription'] = args.resourceDescription
            manifest['references'] = references

        for file in files:
            index = file.rfind('.')
            # fname = file[:index]
            ext = file[index+1:]
            content = {}
            if args.method == 'inline':
                mime = mimetypes.guess_type(file)[0]
                content['mimeType'] = mime
                content['encoding'] = 'base64'
                content['inline'] = file_to_base64(os.path.join(basedir, file))
            else:
                content['path'] = file
            doc = {'document': f"{args.prefix}{file}-{int(time.time())}",
                    'type': args.documentType if args.documentType else ext,
                    'content': content,
                    'properties': {'filename': file}}
            if args.replacesDocument:
                doc['replaces'] = args.replacesDocument
            manifest['documents'].append(doc)

        manifest_path = None
        with tempfile.NamedTemporaryFile(mode='w+t', delete=False, suffix='.json', prefix='manifest-') as tmpfile:
            tmpfile.write(json.dumps(manifest))
            manifest_path = tmpfile.name
        info.append({'manifest': manifest_path})

        if args.method == 'copy':
            # copy the files
            to = f"{args.rawFilesystemMount}/{global_args.realm}"
            os.makedirs(to, exist_ok=True)
            for file in files:
                with new_span('copy', attributes={'file': file}):
                    shutil.copy(os.path.join(basedir, file), to)
        elif args.method == 'scp':
            with paramiko.SSHClient() as remote_client:
                # TODO check if this is secure enough
                if args.autoAddHostKey:
                    remote_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                remote_client.connect(hostname=args.scpHost, username=args.scpUser, password=args.scpPassword, look_for_keys=False, allow_agent=False)
                to = f"{args.scpPath}/{global_args.realm}"
                with remote_client.open_sftp() as ftp_session:
                    for file in files:
                        with new_span('scp', attributes={'file': file}):
                            ftp_session.put(os.path.join(basedir, file), f"{to}/{file}")
                # remote_client.close()

        # Setup auth token
        private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(
            global_args.keystore, global_args.keystorePassword)
        requested_grants = {'txType': 'submit', 'documentCount': len(files)}
        if args.resourceId:
            requested_grants['resourceId'] = args.resourceId
            requested_grants['resourceType'] = args.resourceType
        encoded, payload = issue(private_key, signer_cn, global_args.subject,
                                global_args.audience, 60,  global_args.resource, requested_grants)

        response_json = None
        # Send the request
        if args.method == 'upload':
            # Create form data upload list
            form_files = [('files', ('manifest.json', open(
                manifest_path, 'r'), 'application/json'))]
            for file in files:
                mime = mimetypes.guess_type(file)[0]
                form_files.append(
                    ('files', (file, open(os.path.join(basedir, file), 'rb'), mime)))
            with requests.post(f"{global_args.docriverUrl}/tx/{global_args.realm}",
                            headers={'Authorization': f"Bearer {encoded}", 'Accept': 'application/json'}, verify=not global_args.noverify, files=form_files) as response:
                response.raise_for_status()
                response_json = response.json()
        else:
            with requests.post(f"{global_args.docriverUrl}/tx/{global_args.realm}",
                            json=manifest,
                            headers={'Authorization': f"Bearer {encoded}", 'Accept': 'application/json', 'Content-Type': 'application/json'}, verify=not global_args.noverify) as response:
                response.raise_for_status()
                response_json = response.json()
        
        response_json['info'] = info
        print(to_json(response_json))
        span.set_attribute('txKey', response_json['dr:txId'])
        
def handle_command(args):
    if args.command == 'get':
        handle_get(args)
    elif args.command == 'submit':
        handle_submit(args)

def init_tracing(exp=None, endpoint=None, auth_token_key=None, auth_token_val=None):
    # TODO pass these from environment variables
    resources = {'service.name': 'docriver-client', 'service.version': '1.0.0',
                 'deployment.environment': 'staging'}
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
        tracer = init_tracing(args.otelTraceExp, args.otelTraceExpEndpoint,
                             args.otelTraceAuthTokenKey, args.otelTraceAuthTokenVal)
        handle_command(args)
        trace.get_current_span().set_status(Status(StatusCode.OK))
    except Exception as e:
        err = {'error': str(e)}
        if args and args.debug:
            err['trace'] = str(traceback.format_exc())
        print(to_json(err))
        span = trace.get_current_span()
        span.set_status(Status(StatusCode.ERROR))
        span.record_exception(e)
        sys.exit(1)
