from flask import stream_with_context

from dao.document import get_doc_location
from exceptions import DocumentException
from model.s3_url import parse_url

@stream_with_context
def stream(minio, bucket, path):
    response = None
    try:
        response = minio.get_object(bucket, path)
        while True:
            chunk = response.read(amt=1024)
            if len(chunk) > 0:
                yield chunk
            else:
                return None
    finally:
        response.close()
        response.release_conn()

def stream_document(connection_pool, minio, bucket, realm, document):
    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        location, mime_type = get_doc_location(cursor, realm, document)
        if not location:
            raise DocumentException('Document not found')
        bucket, path = parse_url(location)
        return stream(minio, bucket, path), 200, {'Content-Type': mime_type}
        # return app.response_class(response.stream(), status=response.status, headers=response.getheaders().items())
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()