#!/usr/bin/env python

import argparse
import os
import logging
import sys
import requests
import traceback

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.requests import RequestsInstrumentor

sys.path.append(os.path.abspath(os.path.join(os.getenv('DOCRIVER_GW_HOME'), 'server')))
from auth.keystore import get_entries
from auth.token import issue

tracer = None

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
    parser.add_argument('--resource', default='document',
                        help='resource to authorize')
    parser.add_argument("--realm", required=True, help="Realm to submit document to")
    parser.add_argument('--noverify', action='store_true')
    parser.add_argument("--log", help="log level (valid values are DEBUG, INFO, WARN, ERROR, NONE", default='WARN')
    parser.add_argument('--debug', action='store_true')
    
    parser.add_argument("--otelExp", help="Opentelemetry exporter. Valid values are: none, console and otlp", default=None)
    parser.add_argument("--otelExpEndpoint", help="Opentelemetry exporter endpoint. Only required for OTLP exporter", default=None)

    parser.add_argument("--otelAuthTokenKey", help="Opentelemetry auth token key name", default='auth')
    parser.add_argument("--otelAuthTokenVal", help="Opentelemetry auth token value", default='')
    
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
    elif args.command == 'document':
        handle_get_doc(global_args, args)
    else:
        # Should not happen
        raise Exception('Unknown resource')

def handle_get_doc(global_args, args):
    args = parse_get_doc(args)
    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(global_args.keystore, global_args.keystorePassword)    
    # TODO change to narrower permissions
    encoded, payload = issue(private_key, signer_cn, global_args.subject, global_args.audience, 60,  global_args.resource, {'txType': 'get-document', 'document': '.*'})
    
    with requests.get(f"{global_args.docriverUrl}/document/{global_args.realm}/{args.name}", 
                      headers={'Authorization': f"Bearer {encoded}"}, verify=not global_args.noverify, stream=True) as response:
        response.raise_for_status() 
        with open(args.output, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"Document downloaded to {args.output}")
        
def parse_get_doc(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Output path", required = True)
    parser.add_argument("--name", help="Document name", required = True)
    args = parser.parse_args(args.args)
    return args

def parse_get_events(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--fromTime", help="from time in Epoch seconds", type=int)
    parser.add_argument("--toTime", help="to time in Epoch seconds", type=int)
    args = parser.parse_args(args.args)
    return args

def handle_get_events(global_args, args):
    args = parse_get_events(args)
    private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(global_args.keystore, global_args.keystorePassword)    
    # TODO change to narrower permissions
    encoded, payload = issue(private_key, signer_cn, global_args.subject, global_args.audience, 60,  global_args.resource, {'txType': 'get-events'})
    
    params = {}
    if args.fromTime:
        params['from'] = args.fromTime
    if args.toTime:
        params['to'] = args.toTime
    with requests.get(f"{global_args.docriverUrl}/tx/{global_args.realm}", params=params, headers={'Accept': 'application/json', 'Authorization': f"Bearer {encoded}"}, verify=not global_args.noverify) as response:
        response.raise_for_status() 
        print(response.text)

def init_tracer(exp = None, endpoint = None, auth_token_key=None, auth_token_val=None):
    resources = {'service.name': 'docriver-client', 'service.version': '1.0.0', 
                 'deployment.environment': 'development' }
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
    tracer =  trace.get_tracer("docriver-client")

    RequestsInstrumentor().instrument()
    
    return tracer

if __name__ == '__main__':
    args = None
    try:
        args = parse_toplevel_args()
        #print(args)
        logging.basicConfig(level=args.log)
        
        tracer = init_tracer(args.otelExp, args.otelExpEndpoint, args.otelAuthTokenKey, args.otelAuthTokenVal)
        
        if args.command == 'get':
            handle_get(args)
        else:
            raise Exception('NYI')
    except Exception as e:
        if args and args.debug:
            print(traceback.format_exc(), file=sys.stderr)
        else:
            print(e, file=sys.stderr)
        sys.exit(1)