import time
import base64
import uuid
import io
import logging
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

MIME_EXT_MAP = {
    'text/plain': 'txt',
    'text/html': 'html',
    'application/pdf': 'pdf',
    "application/zip": 'zip',
    "image/jpeg": 'jpg',
    "image/png": 'png'
}

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

def ingest(cnx, minio, bucket, file_mount, payload):
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
        for document in documents:
            # Create a unique document key
            doc_key = "/{}/raw/{}.{}".format(payload['realm'], uuid.uuid1(), 
                MIME_EXT_MAP[document['content']['mimeType']] if document['content']['mimeType'] in MIME_EXT_MAP else 'unk' )

            cursor.execute(DOC_INSERT_SQL, (
            document['operation'] if 'operation' in document else None, 
            document['documentId'], 
            document['version'] if 'version' in document else current_time_ms(), 
            document['type'], tx_id, document['content']['mimeType'],
            "minio:{}:{}".format(bucket, doc_key),
            document['replaces']['documentId'] if 'replaces' in document else None,
            document['replaces']['version'] if 'replaces' in document and 'version' in document['replaces'] else None))
            doc_id = cursor.lastrowid

            # TODO add content validation

            # Write the document to the object store
            stream=None
            if 'data' in document['content']:
                content = decode(document['content']['encoding'] if 'encoding' in document['content'] else None, document['content']['data'])
                stream = io.BytesIO(content)
                put_object(minio, bucket, doc_key, stream, document['content']['mimeType'],
                    document['tags'] if 'tags' in document else None,
                    document['properties'] if 'properties' in document else None)
            elif 'filePath' in document['content']:
                with io.FileIO("{}/{}/raw/{}".format(file_mount, payload['realm'], document['content']['filePath'])) as stream:
                    put_object(minio, bucket, doc_key, stream, document['content']['mimeType'],
                               document['tags'] if 'tags' in document else None,
                               document['properties'] if 'properties' in document else None)
            else:
                raise ValidationException('Unsupported content')

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