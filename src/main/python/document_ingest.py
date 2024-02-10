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
    for document in documents:
        stage_filename = None
        if 'content' in document:
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
            # else: If the inline/path attributes are not specified, then the documentId refers to an existing document
        # else: If the content attribute is not specified, then the documentId refers to an existing document

        if stage_filename:
            document['dr:stageFilename'] = stage_filename
            if 'mimeType' not in document['content']:
                document['content']['mimeType'] = mimetypes.guess_type(document['dr:stageFilename'], strict=False)[0]
            filename_mime_dict[stage_filename] = document['content']['mimeType']
    return filename_mime_dict

def find_matching_document(documents, filename):
    for document in documents:
        if 'content' in document and document['content']['path'] == '/' + filename:
            return document
        # else: the documentId refers to an existing document
    raise None

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

def submit_tx(cnx, minio, bucket, payload):
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
            if 'dr:stageFilename' in document:
                ext = pathlib.Path(document['dr:stageFilename']).suffix
                doc_key = "/{}/raw/{}-{}{}".format(payload['realm'], document['documentId'], document['version'], ext)

                replaces_doc_id = None
                if 'replaces' in document:
                    # Reference to an existing document
                    cursor.execute("""
                        SELECT ID FROM DOC WHERE DOCUMENT = %(replaces)s
                        """, 
                        {"replaces": document['replaces']})
                    row = cursor.fetchone()
                    if not row:
                        raise ValidationException('Non-existent replacement document')
                    replaces_doc_id = row[0]

                cursor.execute(("""
                    INSERT INTO DOC (DOCUMENT, TYPE, MIME_TYPE, REPLACES_DOC_ID) 
                    VALUES (%s, %s, %s, %s)
                    """), 
                    (document['documentId'],  
                    document['type'], 
                    document['content']['mimeType'],
                    replaces_doc_id))
                doc_id = cursor.lastrowid

                if replaces_doc_id:
                    cursor.execute(("""
                        INSERT INTO DOC_EVENT (DESCRIPTION, STATUS, DOC_ID, REF_DOC_ID) 
                        VALUES(%s, %s, %s, %s) 
                        """), 
                        ('REPLACEMENT', 'R', replaces_doc_id, doc_id))

                cursor.execute(("""
                    INSERT INTO DOC_VERSION (DOC_ID, TX_ID, LOCATION_URL)
                    VALUES(%s, %s, %s)
                    """), 
                    (doc_id, tx_id, "minio:{}:{}".format(bucket, doc_key)))

                # Write the document to the object store
                # TODO add more dr:tags to store documentId, etc.
                # TODO move this to the end of this method as any failures will lead to a dangling document in the object store. We cannot really prevent this if this block of code is moved to the bottom, but can reduce the possibilty
                with io.FileIO(document['dr:stageFilename']) as stream:
                    put_object(minio, bucket, doc_key, stream, 
                        document['content']['mimeType'],
                        document['tags'] if 'tags' in document else None,
                        document['properties'] if 'properties' in document else None)
            else:
                # Reference to an existing document
                cursor.execute(("""
                    SELECT ID FROM DOC where DOC = %s"""), 
                    (document['documentId']))
                row = cursor.fetchone()
                if not row:
                    raise ValidationException('Non-existent document')
                doc_id = row[0] 

            cursor.execute(("""
                INSERT INTO DOC_EVENT (DESCRIPTION, STATUS, DOC_ID) 
                VALUES(%s, %s, %s) 
                """), 
                ('INGESTION', 'I', doc_id))

        cursor.execute(("""INSERT INTO TX_EVENT (EVENT, STATUS, TX_ID) 
                  VALUES(%s, %s, %s) 
                  """), 
                  ('INGESTION', 'I', tx_id))
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