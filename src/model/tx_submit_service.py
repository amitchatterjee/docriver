import time
import base64
import io
import os
import os.path
import logging
import mimetypes
import shutil
import pathlib
import fleep

from minio.commonconfig import Tags
import json
from subprocess import PIPE, STDOUT
import uuid
import re

from exceptions import ValidationException
from dao.tx import create_tx, create_tx_event
from dao.document import create_references, create_doc, create_doc_version, create_doc_event, get_doc_by_name
from model.file_validator import validate_documents
from model.common import current_time_ms, format_result_base
from model.authorizer import authorize_submit

def get_payload_from_form(realm, request):
    for field in request.files.keys():
        if not field.startswith('file'):
            continue
        for uploaded_file in request.files.getlist('files'):
            if uploaded_file.filename == 'manifest.json':
                manifest = json.loads(uploaded_file.read())
                if request.form.get('tx', default=None):
                    manifest['tx'] = request.form.get('tx')
                return manifest

    # if we are here, we need to manufacture a manifest provided there is a form entry for the realm
    manifest = {
        'tx': request.form.get('tx', default=str(uuid.uuid4())),
        'documents':[]
    }

    references = {
        'resourceType': request.form.get('refResourceType', default=''),
        'resourceId': request.form.get('refResourceId', default=''),
        'description': request.form.get('refResourceDescription', default='')
    }

    # Remove empty fields
    remove_empty_values(manifest, references)

    types = {}
    for field, value in request.form.items():
        if field.startswith('type'):
            types[field[len('type'):]] = value

    for field in request.files.keys():
        if not field.startswith('file'):
            continue
        suffix = field[len('file'):]
        type = types[suffix] if suffix in types else request.form.get('documentType', default='UNSPECIFIED')
        for uploaded_file in request.files.getlist(field):
            doc = {
                'type': type,
                'document': "{}-{}".format(pathlib.Path(uploaded_file.filename).name, current_time_ms()),
                'content': {
                    'path': uploaded_file.filename
                }
            }
            manifest['documents'].append(doc)

    print(manifest)
    return manifest

def remove_empty_values(manifest, references):
    references = {k:v for k,v in references.items() if v}
    if len(references):
        manifest['references'] = [references]

def validate_manifest(payload):
    if not payload or not 'tx' in payload \
        or not 'documents' in payload \
        or len(payload['documents']) == 0:
        raise ValidationException('Basic validation error')
    
    if not re.match('^[a-zA-Z0-9_\-]+$', payload['tx']):
        raise ValidationException("tx is not valid")
    
    for document in payload['documents']:
        if 'document' not in document or not re.match('^[a-zA-Z0-9_\/\.\-]+$', document['document']):
            raise ValidationException('document not found or document is not valid')
        
        if 'content' in document and 'path' in document['content']:
            if not re.match('^[a-zA-Z0-9_\/\.\-]+$', document['content']['path']):
                raise ValidationException('path is not valid')
        
            if re.match('^[\.]{2,}$', document['content']['path']):
                raise ValidationException('path is not valid - contains ..')
    
def preprocess_manifest(principal, payload):
    for document in payload['documents']:
        document['dr:version'] = current_time_ms()

def decode(encoding, data):
    if not encoding or encoding == 'none':
        return data
    elif encoding == "base64":
        return base64.b64decode(data)
    raise ValidationException('Unsupported encoding')

def put_object(minio, bucket, doc_key, stream, mime_type, tags, properties):
    doc_tags=Tags(for_object=True)
    if (tags):
        doc_tags.update(tags)

    minio.put_object(bucket, doc_key, stream, 
        length=-1, part_size=10*1024*1024, 
        content_type=mime_type, tags=doc_tags, metadata=properties)
    
def stage_documents_from_manifest(principal, stage_dir, raw_file_mount, payload):
    filename_mime_dict = {}
    documents = payload['documents']
    # Assemble all the document in untrusted area for security and other validations
    for document in documents:
        stage_filename = None
        if 'content' in document:
            if 'inline' in document['content']:
                content = decode(document['content']['encoding'] if 'encoding' in document['content'] else None, document['content']['inline'])
                ext = mimetypes.guess_extension(document['content']['mimeType'], True)
                if not ext or ext == '.mp4':
                    # if we were unable to determine an extension based on the mimetype or if it is a mp4 type, look deeper into the content to match a magic signature
                    info = fleep.get(content[0:128])
                    ext = '.' + info.extension[0]
                stage_filename = "{}/{}-{}{}".format(stage_dir,
                    # the following is needed to remove any "directories" if the document id is specified in a path form                 
                    document['document'][document['document'].rfind('/')+1:], 
                    document['dr:version'], ext)
                mode = "w" if document['content']['mimeType'].startswith('text') else "wb"
                with open(stage_filename, mode) as stream:
                    stream.write(content)
            elif 'path' in document['content']:
                src_filename = "{}/{}/{}".format(raw_file_mount, payload['dr:realm'], document['content']['path'])
                stage_filename = "{}/{}".format(stage_dir, os.path.split(src_filename)[1])
                shutil.copyfile(src_filename, stage_filename)
            # else: If the inline/path attributes are not specified, then the document refers to an existing document
        # else: If the content attribute is not specified, then the document refers to an existing document

        if stage_filename:
            document['dr:stageFilename'] = stage_filename
            if 'mimeType' not in document['content']:
                document['content']['mimeType'] = mimetypes.guess_type(document['dr:stageFilename'], strict=False)[0]
            filename_mime_dict[stage_filename] = document['content']['mimeType']
    return filename_mime_dict

def find_matching_document(documents, filename):
    for document in documents:
        if 'content' in document and document['content']['path'] == filename:
            return document
        # else: the document refers to an existing document
    return None

def stage_documents_from_form(principal, request, stage_dir, payload):
    filename_mime_dict = {}
    for field in request.files.keys():
        if not field.startswith('file'):
            continue
        for uploaded_file in request.files.getlist(field):
            if uploaded_file.filename == 'manifest.json':
                continue
            staged_filename = "{}/{}".format(stage_dir, uploaded_file.filename)
            uploaded_file.save(staged_filename)
            document = find_matching_document(payload['documents'], uploaded_file.filename)
            if document:
                document['dr:stageFilename'] = staged_filename
                if 'mimeType' not in document['content']:
                    document['content']['mimeType'] = mimetypes.guess_type(document['dr:stageFilename'], strict=False)[0]
                filename_mime_dict[staged_filename] = document['content']['mimeType']
    return filename_mime_dict

def format_doc_key(payload, document):
    ext = pathlib.Path(document['dr:stageFilename']).suffix
    return "{}/{}-{}{}".format(payload['dr:realm'], document['document'], document['dr:version'], ext)

def write_to_obj_store(principal, minio, bucket, payload):
    documents = payload['documents']
    for document in documents: 
        if 'dr:stageFilename' in document:
            # TODO add more dr:tags to store document, etc.
            # TODO the code below is not transactional. That means if a file put fails, the minio storage will be in a messed up state. We can perform cleanups since we have the references in the metadata store. A better way to do this is to tar the files and have minio extract it - https://blog.min.io/minio-optimizes-small-objects/
            with io.FileIO(document['dr:stageFilename']) as stream:
                    put_object(minio, bucket, format_doc_key(payload, document), stream, 
                        document['content']['mimeType'],
                        document['tags'] if 'tags' in document else None,
                        document['properties'] if 'properties' in document else None)

def write_metadata(principal, connection, bucket, payload):
    cursor = connection.cursor()
    try:
        tx_id = create_tx(payload, 'submit', cursor)
        payload['dr:txId'] = tx_id
        create_tx_event(cursor, tx_id)
        
        documents = payload['documents']
        for document in documents:
            doc_id, version_id, doc_status = get_doc_by_name(cursor, payload['dr:realm'], document['document'])            

            if 'dr:stageFilename' in document:
                new_version = 'replaces' in document and document['replaces'] == document['document']

                if not new_version and doc_id and doc_status not in ['R', 'D']:
                    raise ValidationException('The document already exists')
            
                if 'replaces' in document:
                    replaces_doc_id = None
                    if document['replaces'] != document['document']:
                        replaces_doc_id, replaces_version_id, replaces_doc_status = get_doc_by_name(cursor, payload['dr:realm'], document['replaces'])
                        if replaces_doc_id == None or replaces_doc_status in ['R', 'D']:
                            raise ValidationException('Non-existent or replaced replacement document: {}'.format(document['replaces']))

                if not doc_id:
                    # The document may already exist becaause a previous document with the same name has been replaced/voided or this is a "self-replacement" document (new version)
                    doc_id = create_doc(cursor, document, payload['dr:realm'])

                version_id = create_doc_version(bucket, cursor, tx_id, doc_id, format_doc_key(payload, document), document)

                if 'replaces' in document:
                    if new_version:
                        # Self replacement
                        create_doc_event(cursor, tx_id, doc_id, None, 'NEW_VERSION', 'V')
                    else:
                        create_doc_event(cursor, tx_id, replaces_doc_id, doc_id, 'REPLACEMENT', 'R')
            else:
                # Reference to an existing document
                if not doc_id or doc_status in ['R', 'D']:
                    raise ValidationException("Document: {} not found or has been replaced".format(document['document']))

            create_doc_event(cursor, tx_id, doc_id, None, 
                             'INGESTION' if 'dr:stageFilename' in document else 'REFERENCE', 
                             'I' if 'dr:stageFilename' in document else 'J')

            if 'references' in payload:
                create_references(cursor, payload['references'], version_id)

            if 'references' in document:
                create_references(cursor, document['references'], version_id)

            document['dr:documentId'] = doc_id
            document['dr:documentVersionId'] = version_id
    finally:
        cursor.close()

def stage_dirname(untrusted_file_mount):
    return "{}/{}".format(untrusted_file_mount, uuid.uuid1())

def format_result(start, payload, end):
    result = format_result_base(start, payload, end)
    if 'authorization' in result:
        result['authorization'] = '<snipped>'
    for document in result['documents']:
        if 'content' in document and 'inline' in document['content']:
            document['content']['inline'] = '<snipped>'
    return result

def submit_docs_tx(untrusted_fs_mount, raw_fs_mount, scanner_fs_mount, bucket, connection_pool, minio, scanner, public_keys, audience, realm, request):
    start = current_time_ms() 
    connection = connection_pool.get_connection()
    stage_dir = stage_dirname(untrusted_fs_mount)
    try:
        payload = None
        rest = request.content_type == 'application/json'
        if rest:
            payload = request.json
        else:
            # Assume multipart/form or multipart/mixed
            payload = get_payload_from_form(realm, request)

        payload['dr:realm'] = realm
        validate_manifest(payload)

        token = payload['authorization'] if 'authorization' in payload else request.headers.get('Authorization')
        authorize_submit(public_keys, token, audience, payload)

        logging.info("Received submission request: {}/{}. Content-Type: {}, accept: {}, principal: {}".format(payload['dr:realm'], payload['tx'], request.content_type, request.headers.get('Accept', default='text/html'), payload['dr:principal']))

        os.makedirs(stage_dir)

        preprocess_manifest(payload['dr:principal'],payload)

        filename_mime_dict = None
        if rest:
            filename_mime_dict = stage_documents_from_manifest(payload['dr:principal'], stage_dir, raw_fs_mount, payload)
        else:
            filename_mime_dict = stage_documents_from_form(payload['dr:principal'],request, stage_dir, payload)

        validate_documents(payload['dr:principal'], scanner, scanner_fs_mount, stage_dir, filename_mime_dict)
        write_metadata(payload['dr:principal'], connection, bucket, payload)
        write_to_obj_store(payload['dr:principal'], minio, bucket, payload)

        end = current_time_ms()
        result = format_result(start, payload, end)
        
        connection.commit()
        return result
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        if os.path.isdir(stage_dir):
            shutil.rmtree(stage_dir)
        if connection.is_connected():
            connection.close()