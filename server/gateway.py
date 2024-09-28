#!/usr/bin/env python

import mysql.connector
from minio import Minio
import argparse
import logging
import clamd
import sys

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.mysql import MySQLInstrumentor

from controller.http import init_app, init_params
from auth.keystore import get_entries

def init_db(host, port, db, user, password, pool_size):
    # Instrument MySQL conections
    MySQLInstrumentor().instrument()
    
    return mysql.connector.pooling.MySQLConnectionPool(pool_name='docriver', 
            pool_size=pool_size,
            user=user, password=password,
            host=host,
            port=port,
            database=db)

def init_obj_store(url, access_key, secret_key):
    # TODO fix the secure=False
    return Minio(url, secure=False, access_key=access_key, secret_key=secret_key)
    
def init_virus_scanner(host, port):
    return clamd.ClamdNetworkSocket(host=host, port=port)

def init_authorization(keystore, password):
    if not keystore:
        # authorization is not enabled
         logging.getLogger('Authorization').warning("Authorization disabled!!!")
         return None, None, None, None, None
    return get_entries(keystore, password)

def init_tracer(exp = None, endpoint = None, auth_token_key=None, auth_token_val=None):
    resources = {}
    if auth_token_key:
        resources[auth_token_key] = auth_token_val
        
    resource = Resource.create(resources)    
    
    provider = TracerProvider(resource=resource)
    if exp == 'console':
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
    elif exp == 'otlp':
        processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        provider.add_span_processor(processor)
    else:
        logging.getLogger('Tracer').warning("Tracer disabled!!!")

    # Sets the global default tracer provider
    trace.set_tracer_provider(tracer_provider=provider)

    # Creates a tracer from the global tracer provider
    # TODO make the name cofigurable
    tracer = trace.get_tracer("docriver-gateway")
    
    return tracer

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--httpPort", type=int, help="HTTP port number", default=5000)

    parser.add_argument("--objUrl", help="URL of the object store", default='localhost:9000')
    parser.add_argument("--objAccessKey", help="Access key of the object store", default='docriver-key')
    parser.add_argument("--objSecretKey", help="Secret key for the object store", default='docriver-secret')
    parser.add_argument("--bucket", help="Bucket name where the documents are stored", default='docriver')

    parser.add_argument("--rawFilesystemMount", help="mount point of the shared filesystem where raw documents is stored by applications. The applications can copy files to this location and specify the location instead of uploading", default='.')
    parser.add_argument("--untrustedFilesystemMount", help="mount point of a shared filesystem where untrusted files are staged for validations, virus scans, etc. This mount point must be shared with the virus scanner", default='.')
    
    parser.add_argument("--dbPoolSize", help="Connection pool size", type=int, default=5)
    parser.add_argument("--dbHost", help="Database host name", default='127.0.0.1')
    parser.add_argument("--dbPort", type=int, help="Database port number", default=3306)
    parser.add_argument("--dbUser", help="Database user name", default='docriver')
    parser.add_argument("--dbPassword", help="Database password", default='docriver')
    parser.add_argument("--dbDatabase", help="Database name", default='docriver')

    parser.add_argument("--scanHost", help="Document virus checker hostname", default='127.0.0.1')
    parser.add_argument("--scanPort", type=int, help="Document virus checker port number", default=3310)
    parser.add_argument("--scannerFilesystemMount", help="Mount point for the untrusted area in the scanner server", default='/scandir')

    parser.add_argument('--authKeystore', default=None,
                        help='A PKCS12 keystore file for storing certifcates and keys for authorizing transactions')
    parser.add_argument('--authPassword', default=None,
                        help='Authorization keystore password')
    parser.add_argument('--authAudience', default='docriver',
                        help='Target application for authorization')

    parser.add_argument('--tlsKey', default=None,
                        help="A file containing the site's TLS private key (PEM)")
    parser.add_argument('--tlsCert', default=None,
                        help="A file containing the site's TLS certificate (PEM)")

    parser.add_argument("--log", help="log level (valid values are INFO, WARNING, ERROR, NONE", default='WARN')
    parser.add_argument('--debug', action='store_true')

    parser.add_argument("--otelExp", help="Opentelemetry exporter. Valid values are: none, console and otlp", default=None)
    parser.add_argument("--otelExpEndpoint", help="Opentelemetry exporter endpoint. Only required for OTLP exporter", default=None)

    parser.add_argument("--otelAuthTokenKey", help="Opentelemetry auth token key name", default='auth')
    parser.add_argument("--otelAuthTokenVal", help="Opentelemetry auth token value", default='')

    args = parser.parse_args(args)
    # TODO add validation

    return args

if __name__ == '__main__':
    args = parse_args(sys.argv[1:])
    logging.basicConfig(level=args.log)
    
    tracer = init_tracer(args.otelExp, args.otelExpEndpoint, args.otelAuthTokenKey, args.otelAuthTokenVal)
    
    connection_pool = init_db(args.dbHost, args.dbPort, args.dbDatabase, args.dbUser, args.dbPassword, args.dbPoolSize)
    minio = init_obj_store(args.objUrl, args.objAccessKey, args.objSecretKey)
    scanner = init_virus_scanner(args.scanHost, args.scanPort)
    auth_private_key, auth_public_key, auth_signer_cert, auth_signer_cn, auth_public_keys = init_authorization(args.authKeystore, args.authPassword)

    app = init_app()
    
    FlaskInstrumentor().instrument_app(app, excluded_urls="health")

    init_params(connection_pool, minio, scanner, tracer, args.bucket, args.untrustedFilesystemMount, args.rawFilesystemMount, args.scannerFilesystemMount, auth_private_key, auth_public_key, auth_signer_cert, auth_signer_cn, auth_public_keys, args.authAudience)

    if args.tlsKey:
        logging.info("Starting server in TLS mode - cert: {}, key: {}".format(args.tlsCert, args.tlsKey))
        app.run(host="0.0.0.0", ssl_context=(args.tlsCert, args.tlsKey), port=args.httpPort, debug=args.debug)
    else:
        logging.warning("Starting server in non-TLS mode")
        app.run(host="0.0.0.0", port=args.httpPort, debug=args.debug)

