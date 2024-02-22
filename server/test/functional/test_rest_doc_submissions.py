import os
import shutil
import pytest
import logging
import base64
from controller.http import init_app, init_params
from main import init_db, init_obj_store, init_virus_scanner

TEST_REALM = 'test123456'

def rmmkdir(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def delete_obj_recursively(minio, bucketname, folder):
    objs = minio.list_objects(bucketname, prefix=folder, recursive=True)
    for obj in objs:
        minio.remove_object(bucketname, obj.object_name)

@pytest.fixture(scope="session", autouse=True)
def connection_pool():
    return init_db(os.getenv('DOCRIVER_MYSQL_HOST', default='127.0.0.1'), 
                   os.getenv('DOCRIVER_MYSQL_PORT', default=3306), 
                   os.getenv('DOCRIVER_MYSQL_USER', default='docriver'), 
                   os.getenv('DOCRIVER_MYSQL_PASSWORD', default='docriver'), 
                   'docriver', 5)

@pytest.fixture(scope="session", autouse=True)
def minio():
    return init_obj_store('localhost:9000', 'docriver-key', 'docriver-secret')

@pytest.fixture(scope="session", autouse=True)
def scanner():
    return init_virus_scanner('127.0.0.1', 3310)

@pytest.fixture(scope="session", autouse=True)
def client(connection_pool, minio, scanner):
    logging.getLogger().setLevel('INFO')
    raw='../target/volumes/raw'
    rmmkdir(raw)

    untrusted = os.getenv('DOCRIVER_UNTRUSTED_ROOT')

    app = init_app()
    app.config['TESTING'] = True
    init_params(connection_pool, minio, scanner, 'docriver', untrusted, raw, '/scandir')

    with app.test_client() as client:
        yield client

@pytest.fixture()
def cleanup(connection_pool, minio):
    connection = connection_pool.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute('DELETE FROM TX')
        cursor.execute('DELETE FROM DOC')
        connection.commit()

        delete_obj_recursively(minio, 'docriver', TEST_REALM)
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def test_health(client):
    response = client.get('/health')
    assert response.json['system'] == 'UP'

def test_inline_encoding_plain(cleanup, client):
    response = client.post('/tx', json=inline_doc('Hello world', '1', 'd001', None, 'text/plain'),
                           headers={'Accept': 'application/json'})
    assert response.status_code == 200
    assert response.json['dr:status'] == 'ok'

def test_inline_encoding_html(cleanup, client):
    response = client.post('/tx', json=inline_doc('<body><b>Hello world</b></body>', '1', 'd001', None, 'text/html'),
                           headers={'Accept': 'application/json'})
    assert response.status_code == 200
    assert response.json['dr:status'] == 'ok'

def test_inline_encoding_pdf(cleanup, client):
    with open("test/resources/documents/sample.pdf", "rb") as pdf_file:
        inline = base64.b64encode(pdf_file.read())
    response = client.post('/tx', 
                           json=inline_doc(inline.decode('utf-8'), '1', 'd001',  'base64', 'application/pdf',), 
                           headers={'Accept': 'application/json'})
    assert response.status_code == 200
    assert response.json['dr:status'] == 'ok'

def inline_doc(inline, tx, doc, encoding, mime_type):
    return {
        'tx': tx,
        'realm': TEST_REALM,
        'documents': [
            {
                'document': doc,
                'type': 'sample',
                'content': {
                    'mimeType': mime_type,
                    'encoding': encoding,
                    'inline': inline
                }
            }
        ]
    }
    