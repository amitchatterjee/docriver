from flask import stream_with_context

@stream_with_context
def stream(minio, bucket, realm, document):
    response = None
    try:
        response = minio.get_object('docriver', 'test123456/raw/doc-1-1712342308871.jpg')
        while True:
            chunk = response.read(amt=1024)
            if len(chunk) > 0:
                yield chunk
            else:
                return None
    finally:
        response.close()
        response.release_conn()

def stream_document(minio, bucket, realm, document):
    return stream(minio, bucket, realm, document), 200, {'Content-Type': 'image/jpeg'}
    # return app.response_class(response.stream(), status=response.status, headers=response.getheaders().items())