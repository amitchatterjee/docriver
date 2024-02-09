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
from os import listdir
from os.path import isfile, join
import json
import subprocess
from subprocess import PIPE, STDOUT
import clamd

from exceptions import ValidationException

def current_time_ms():
    return round(time.time() * 1000)

def get_payload_from_form(request):
    for uploaded_file in request.files.getlist('files'):
        if uploaded_file.filename == 'manifest.json':
            manifest = uploaded_file.read()
            return json.loads(manifest)
    raise ValidationException('manifest file not found')

def validate_manifest(payload):
    if not payload or not 'txId' in payload \
        or not 'realm' in payload \
        or not 'documents' in payload \
        or len(payload['documents']) == 0:
        raise ValidationException('Validation error')
    
def preprocess_manifest(payload):
    documents = payload['documents']
    # Assemble all the document in untrusted area for security and other validations
    for document in documents:
        if 'version' not in document:
            document['version'] = current_time_ms()

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


# doc_key = "/{}/raw/{}-{}{}".format(payload['realm'], document['documentId'], document['version'], ext)
# document['dr:docKey'] = doc_key
    
def stage_documents_from_manifest(stage_dir, raw_file_mount, payload):
    filename_mime_dict = {}
    documents = payload['documents']
    # Assemble all the document in untrusted area for security and other validations
    stage_filename = None
    for document in documents:
        if 'inline' in document['content']:
            ext = mimetypes.guess_extension(document['content']['mimeType'], False) 
            ext = ext if ext else '.unk'            
            stage_filename = "{}/{}-{}{}".format(stage_dir, document['documentId'], document['version'], ext)
            content = decode(document['content']['encoding'] if 'encoding' in document['content'] else None, document['content']['inline'])
            # TODO this may not be a binary file. Using mimetype, determine if the file is binary or not and use "w" va. "wb"
            with open(stage_filename, "wb") as stream:
                stream.write(content)
        elif 'path' in document['content']:
            src_filename = "{}/{}/{}".format(raw_file_mount, payload['realm'], document['content']['path'])
            stage_filename = "{}/{}".format(stage_dir, os.path.split(src_filename)[1])
            shutil.copyfile(src_filename, stage_filename)
        else:
            raise ValidationException('Unsupported content')
        document['dr:stageFilename'] = stage_filename
        if 'mimeType' not in document['content']:
            document['content']['mimeType'] = mimetypes.guess_type(document['dr:stageFilename'], strict=False)[0]
        filename_mime_dict[stage_filename] = document['content']['mimeType']
    return filename_mime_dict

def find_matching_document(documents, filename):
    for document in documents:
        if document['content']['path'] == '/' + filename:
            return document
    raise ValidationException('file not found')

def stage_documents_from_form(request, stage_dir, payload):
    filename_mime_dict = {}
    for uploaded_file in request.files.getlist('files'):
        if uploaded_file.filename == 'manifest.json':
            continue
        staged_filename = "{}/{}".format(stage_dir, uploaded_file.filename)
        uploaded_file.save(staged_filename)
        document = find_matching_document(payload['documents'], uploaded_file.filename)
        document['dr:stageFilename'] = staged_filename
        if 'mimeType' not in document['content']:
            document['content']['mimeType'] = mimetypes.guess_type(document['dr:stageFilename'], strict=False)[0]
        filename_mime_dict[staged_filename] = document['content']['mimeType']
    return filename_mime_dict

def validate_documents(scanner, scan_file_mount, stage_dir, filename_mime_dict):
    for file in listdir(stage_dir):
        full_path = join(stage_dir, file)
        if isfile(full_path):
            if mimetypes.guess_type(full_path)[0].startswith('text'):
                # Skip for text file. TODO The way we detect it here is not great. Improve text file detection
                continue
            # For binary files, use magic to detect file types
            with open(full_path, 'rb') as stream:
                ext = pathlib.Path(full_path).suffix
                content = stream.read(128)
                info = fleep.get(content)
                if not info.extension_matches(ext[1:]):
                     raise ValidationException("Magic mismatch for extension in file: {}. Expected: {}, found:{}".format(file, ext, info.extension))
                if not info.mime_matches(filename_mime_dict[full_path]):
                     raise ValidationException("Magic mismatch for mimeType in file: {}. Expected: {}, found:{}".format(file, ext, info.extension))
                # print('Type:', info.type)
                # print('File extension:', info.extension[0])
                # print('MIME type:', info.mime[0]) 

    # TODO this code is temporary
    # command="""
    #    docker run -it --rm --name clamdscan --network dl --mount type=bind,source={},target=/scandir --mount type=bind,source=$HOME/git/docriver/src/test/conf/# clam.remote.conf,target=/conf/clam.remote.conf  clamav/clamav:stable_base clamdscan --fdpass --verbose --stdout -c /conf/clam.remote.conf /scandir
    # """.format(stage_dir)
    # result = subprocess.run(command, shell=True, stderr=STDOUT, stdout=PIPE, text=True, check=True)
    # print(result.stdout)
    # logging.getLogger().info("Scan result: ", result.stdout)
    # os.system(command) 

    # This assumes that the staging area is created just below the untrusted filesystem mount
    result = scanner.scan(join(scan_file_mount, pathlib.Path(stage_dir).name))
    for kv in result.items():
        if kv[1][0] != 'OK':
            raise ValidationException("Virus check failed on file: {}. Error: {}".format(pathlib.Path(kv[0]).name, kv[1]))

def ingest_tx(cnx, minio, bucket, payload):
    connection = cnx.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(("INSERT INTO TX (TX, REALM) VALUES (%s, %s)"), (payload['txId'], payload['realm']))
        tx_id = cursor.lastrowid

        if 'references' in payload:
            for reference in payload['references']:
                cursor.execute(("""
                    INSERT INTO REF (RESOURCE_TYPE, RESOURCE_ID, DESCRIPTION, TX_ID) 
                    VALUES(%s, %s, %s, %s) 
                    """), 
                  (reference['resourceType'], 
                    reference ['resourceId'],
                    reference['description'] if 'description' in reference else None, 
                    tx_id))
                ref_id = cursor.lastrowid
                if 'properties' in reference:
                    for k,v in reference['properties'].items():
                        cursor.execute( ("""
                                INSERT INTO REF_PROPERTY (REF_ID, KEY_NAME, VALUE) VALUES(%s, %s, %s)
                             """), 
                             (ref_id, k, v))

        documents = payload['documents']
        for document in documents: 
            ext = pathlib.Path(document['dr:stageFilename']).suffix
            doc_key = "/{}/raw/{}-{}{}".format(payload['realm'], document['documentId'], document['version'], ext)

            cursor.execute(("""
                    INSERT INTO DOC (OPERATION, DOC_ID, VERSION, TYPE, TX_ID,
                    MIME_TYPE, LOCATION_URL, REPLACES_DOC_ID, REPLACES_VERSION) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """), 
                (document['operation'] if 'operation' in document else None, 
                document['documentId'], 
                document['version'], 
                document['type'], 
                tx_id, 
                document['content']['mimeType'],
                "minio:{}:{}".format(bucket, doc_key),
                document['replaces']['documentId'] if 'replaces' in document else None,
                document['replaces']['version'] if 'replaces' in document and 'version' in document['replaces'] else None))
            doc_id = cursor.lastrowid

            # Write the document to the object store
            # TODO add more dr:tags to store documentId, etc.
            with io.FileIO(document['dr:stageFilename']) as stream:
                put_object(minio, bucket, doc_key, stream, 
                    document['content']['mimeType'],
                    document['tags'] if 'tags' in document else None,
                    document['properties'] if 'properties' in document else None)

            cursor.execute(("""
                INSERT INTO DOC_EVENT (EVENT, STATUS, DOC_ID) 
                VALUES(%s, %s, %s) 
                """), 
                ('INGESTION', 'C', doc_id))
        cursor.execute(("""INSERT INTO TX_EVENT (EVENT, STATUS, TX_ID) 
                  VALUES(%s, %s, %s) 
                  """), 
                  ('INGESTION', 'C', tx_id))
        connection.commit()
        return tx_id
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        cursor.close()
        connection.close()

# from datetime import datetime, timezone
# from minio.commonconfig import REPLACE, CopySource
# copy an object from a bucket to another.
# result = client.copy_object(
#    "my-bucket",
#    "my-object",
#    CopySource("my-sourcebucket", "my-sourceobject"),
#)
#print(result.object_name, result.version_id)