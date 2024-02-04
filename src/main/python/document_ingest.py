import time
import base64
import io
import os
import os.path
import logging
import mimetypes
import shutil
import string
from minio.commonconfig import Tags

from exceptions import ValidationException

def current_time_ms():
    return round(time.time() * 1000)

def validate_manifest(payload):
    if not payload or not 'txId' in payload \
        or not 'realm' in payload \
        or not 'documents' in payload \
        or len(payload['documents']) == 0:
        raise ValidationException('Validation error')

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


def stage_and_validate_documents(untrusted_file_mount, raw_file_mount, payload):
    documents = payload['documents']
    stage_dir = stage_dirname(untrusted_file_mount, payload)
    os.makedirs(stage_dir, exist_ok=True)

    # Assemble all the document in untrusted area for security and other validations
    for document in documents:
        ext = mimetypes.guess_extension(document['content']['mimeType'], False) 
        ext = ext if ext else '.unk'
        version = document['version'] if 'version' in document else current_time_ms()
        if 'version' not in document:
            document['version'] = version

        doc_key = "/{}/raw/{}-{}{}".format(payload['realm'], document['documentId'], version, ext)
        document['dr:docKey'] = doc_key
        stage_filename = "{}/{}-{}{}".format(stage_dir, document['documentId'], version, ext)
        document['dr:stageFilename'] = stage_filename

        if not os.path.isfile(stage_filename):
            if 'data' in document['content']:
                content = decode(document['content']['encoding'] if 'encoding' in document['content'] else None, document['content']['data'])
                # TODO this may not be a binary file. Using mimetype, determine if the file is binary or not and use "w" va. "wb"
                with open(stage_filename, "wb") as ostream:
                    ostream.write(content)
            elif 'filePath' in document['content']:
                shutil.copyfile("{}/{}/{}".format(raw_file_mount, payload['realm'], document['content']['filePath']), stage_filename)
            else:
                raise ValidationException('Unsupported content')
         # TODO add content validation
        
        return stage_dir

def stage_dirname(untrusted_file_mount, payload):
    return "{}/{}/{}".format(untrusted_file_mount, payload['realm'], payload['txId'])

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
                        cursor.execute( ("""INSERT INTO REF_PROPERTIES (REF_ID, KEY_NAME, VALUE) 
                                VALUES(%s, %s, %s)
                             """), 
                             (ref_id, k, v))

        documents = payload['documents']
        for document in documents:            
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
                "minio:{}:{}".format(bucket, document['dr:docKey']),
                document['replaces']['documentId'] if 'replaces' in document else None,
                document['replaces']['version'] if 'replaces' in document and 'version' in document['replaces'] else None))
            doc_id = cursor.lastrowid

            # Write the document to the object store
            # TODO add more dr:tags to store documentId, etc.
            with io.FileIO(document['dr:stageFilename']) as stream:
                put_object(minio, bucket, document['dr:docKey'], stream, 
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