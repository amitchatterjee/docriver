import time
import base64
import io
import os
import logging
import mimetypes
import shutil
import string
from minio.commonconfig import Tags

from exceptions import ValidationException

TX_INSERT_SQL = ("INSERT INTO TX (TX, REALM) VALUES (%s, %s)")
DOC_INSERT_SQL = ("""INSERT INTO DOC (OPERATION, DOC_ID, VERSION, TYPE, TX_ID,
                   MIME_TYPE, LOCATION_URL, REPLACES_DOC_ID, REPLACES_VERSION) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                  """)
REF_INSERT_SQL = ("""INSERT INTO REF (RESOURCE_TYPE, RESOURCE_ID, DESCRIPTION, TX_ID) 
                  VALUES(%s, %s, %s, %s) 
                  """)

TX_EVENT_INSERT_SQL = ("""INSERT INTO TX_EVENT (EVENT, STATUS, TX_ID) 
                  VALUES(%s, %s, %s) 
                  """)

DOC_EVENT_INSERT_SQL = ("""INSERT INTO DOC_EVENT (EVENT, STATUS, DOC_ID) 
                  VALUES(%s, %s, %s) 
                  """)

REF_PROPERTIES_INSERT_SQL = ("""INSERT INTO REF_PROPERTIES (REF_ID, KEY_NAME, VALUE) 
                                VALUES(%s, %s, %s)
                             """)

def current_time_ms():
    return round(time.time() * 1000)

def validate(payload):
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

def ingest(cnx, minio, bucket, raw_file_mount, untrusted_file_mount, payload):
    connection = cnx.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(TX_INSERT_SQL, (payload['txId'], payload['realm']))
        tx_id = cursor.lastrowid

        if 'references' in payload:
            for reference in payload['references']:
                cursor.execute(REF_INSERT_SQL, (reference['resourceType'], 
                    reference ['resourceId'],
                    reference['description'] if 'description' in reference else None, 
                    tx_id))
                ref_id = cursor.lastrowid
                if 'properties' in reference:
                    for k,v in reference['properties'].items():
                        cursor.execute(REF_PROPERTIES_INSERT_SQL, (ref_id, k, v))

        documents = payload['documents']

        stage_dir = "{}/{}/{}".format(untrusted_file_mount, payload['realm'], payload['txId'])
        os.makedirs(stage_dir)

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

        for document in documents:            
            cursor.execute(DOC_INSERT_SQL, (
                document['operation'] if 'operation' in document else None, 
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
            with io.FileIO(document['dr:stageFilename']) as stream:
                put_object(minio, bucket, document['dr:docKey'], stream, 
                    document['content']['mimeType'],
                    document['tags'] if 'tags' in document else None,
                    document['properties'] if 'properties' in document else None)
                
            cursor.execute(DOC_EVENT_INSERT_SQL, ('INGESTION', 'C', doc_id))

        cursor.execute(TX_EVENT_INSERT_SQL, ('INGESTION', 'C', tx_id))
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