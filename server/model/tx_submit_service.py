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
from dao.document import create_references, create_doc, create_doc_version, create_doc_event, get_doc_and_version_by_name, get_doc_by_name
from model.file_validator import validate_documents

def current_time_ms():
    return round(time.time() * 1000)

def get_payload_from_form(request):
    for uploaded_file in request.files.getlist('files'):
        if uploaded_file.filename == 'manifest.json':
            manifest_file = uploaded_file.read()
            return json.loads(manifest_file)
    # if we are here, we need to manufacture a manifest provided there is a form entry for the realm
    if 'realm' not in request.form:
        raise ValidationException('manifest file not found and realm not specified in the form field')
    manifest = {
        'realm': request.form['realm'],
        'tx': request.form.get('tx', default=str(uuid.uuid4())),
        'documents':[]
    }

    ref_dict = {
        'resourceType': request.form.get('refResourceType', default=''),
        'resourceId': request.form.get('refResourceId', default=''),
        'description': request.form.get('refResourceDescription', default='')
    }
    # Remove empty fields
    ref_dict = {k: v for k, v in ref_dict.items() if v}
    if len(ref_dict):
        manifest['references'] = [ref_dict]

    for uploaded_file in request.files.getlist('files'):
        doc = {
            'type': request.form.get('documentType', default='UNSPECIFIED'),
            'document': "{}-{}".format(pathlib.Path(uploaded_file.filename).name, current_time_ms()),
            'content': {
                'path': uploaded_file.filename
            }
        }
        manifest['documents'].append(doc)
    # print(manifest)
    return manifest

def validate_manifest(payload):
    if not payload or not 'tx' in payload \
        or not 'realm' in payload \
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
    
def preprocess_manifest(payload):
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
    
def stage_documents_from_manifest(stage_dir, raw_file_mount, payload):
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
                src_filename = "{}/{}/{}".format(raw_file_mount, payload['realm'], document['content']['path'])
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

def stage_documents_from_form(request, stage_dir, payload):
    filename_mime_dict = {}
    for uploaded_file in request.files.getlist('files'):
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
    return "{}/raw/{}-{}{}".format(payload['realm'], document['document'], document['dr:version'], ext)

def write_to_obj_store(minio, bucket, payload):
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

def write_metadata(connection, bucket, payload):
    cursor = connection.cursor()
    try:
        tx_id = create_tx(payload, cursor)
        payload['dr:txId'] = tx_id
        create_tx_event(cursor, tx_id)
        
        documents = payload['documents']
        for document in documents:
            doc_id = None
            self_replace = False
            if 'dr:stageFilename' in document:
                replaces_doc_id = None
                if 'replaces' in document:
                    # Reference to an existing document

                    # TODO if the document has already been replaced, we should not allow a replacement
                    replaces_doc_id = get_doc_by_name(cursor, document['replaces'])
                    if replaces_doc_id == None:
                        raise ValidationException('Non-existent replacement document: {}'.format(document['replaces']))

                    if document['replaces'] == document['document']:
                        # if the document is replacing self
                        self_replace = True
                        doc_id = replaces_doc_id

                if not self_replace:
                    # If the document has not already been created (replacing self case)
                    doc_id = create_doc(cursor, document, replaces_doc_id)

                version_id = create_doc_version(bucket, cursor, tx_id, doc_id, format_doc_key(payload, document))

                if replaces_doc_id:
                    if self_replace:
                        create_doc_event(cursor, tx_id, doc_id, None, 'NEW_VERSION', 'V')
                    else:
                        create_doc_event(cursor, tx_id, replaces_doc_id, doc_id, 'REPLACEMENT', 'R')
            else:
                # Reference to an existing document
                doc_and_version = get_doc_and_version_by_name(cursor, document['document'])
                if doc_and_version == None:
                    raise ValidationException("Document: {} not found".format(document['document']))
                doc_id, version_id = doc_and_version['doc'], doc_and_version['version']

            create_doc_event(cursor, tx_id, doc_id, None, 
                             'INGESTION' if 'dr:stageFilename' in document else 'REFERENCE', 
                             'I' if 'dr:stageFilename' in document else 'J')

            if 'references' in payload:
                create_references(cursor, payload['references'], version_id)

            if 'references' in document:
                create_references(cursor, document['references'], version_id)

            document['dr:document'] = doc_id
            document['dr:documentVersionId'] = version_id
    finally:
        cursor.close()

def format_result(start, payload, end):
    result = {'dr:status': 'ok', 'dr:took': end - start}
    for document in payload['documents']:
        if 'content' in document and 'inline' in document['content']:
            document['content']['inline'] = '<snipped>'
    result.update(payload)
    return result

def stage_dirname(untrusted_file_mount):
    return "{}/{}".format(untrusted_file_mount, uuid.uuid1())

def format_result(start, payload, end):
    result = {'dr:status': 'ok', 'dr:took': end - start}
    for document in payload['documents']:
        if 'content' in document and 'inline' in document['content']:
            document['content']['inline'] = '<snipped>'
    result.update(payload)
    return result

def new_tx(untrusted_fs_mount, raw_fs_mount, scanner_fs_mount, bucket, connection_pool, minio, scanner, request):
    start = current_time_ms()
    rest = request.content_type == 'application/json'
    payload = None
    stage_dir = stage_dirname(untrusted_fs_mount)
    connection = connection_pool.get_connection()
    try:
        if rest:
            payload = request.json
        else:
            # Assume multipart/form or multipart/mixed
            payload = get_payload_from_form(request)

        validate_manifest(payload)

        os.makedirs(stage_dir)
        logging.info("Received submission request: {}/{}. Content-Type: {}, Accept: {}".format(payload['realm'], payload['tx'], request.content_type, request.headers.get('Accept', default='text/html')))

        preprocess_manifest(payload)

        filename_mime_dict = None
        if rest:
            filename_mime_dict = stage_documents_from_manifest(stage_dir, raw_fs_mount, payload)
        else:
            filename_mime_dict = stage_documents_from_form(request, stage_dir, payload)

        validate_documents(scanner, scanner_fs_mount, stage_dir, filename_mime_dict)
        write_metadata(connection, bucket, payload)
        write_to_obj_store(minio, bucket, payload)

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