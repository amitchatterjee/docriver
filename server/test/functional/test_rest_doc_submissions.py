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


def to_base64(filename):
    with open(filename, "rb") as file:
        inline = base64.b64encode(file.read())
    return inline.decode('utf-8')

def inline_doc(inline, tx, doc, encoding, mime_type):
    # saved_args = locals()
    # print("args:", saved_args)
    if inline.startswith('file:'):
        filename = inline[inline.find(':')+1:]
        if encoding == 'base64':            
            inline = to_base64(filename)
        else:
            with open(filename, "r") as file:
                inline = file.read()
    # print(inline)
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

def submit_inline_doc(client, parameters):
    response = client.post('/tx', json=inline_doc(*parameters),
                           headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8')

def test_health(client):
    response = client.get('/health')
    assert response.json['system'] == 'UP'

# The parameters are (test_name, (inline_text, tx, document, encoding, mime_type), (expected_http_status, expected_dr_status))
@pytest.mark.parametrize("test_case, input, expected", [
    ('plain text', ('Hello world', '1', 'd001', None, 'text/plain'), (200, 'ok')),
    ('html', ('<body><b>Hello world</b></body>', '2', 'd002', None, 'text/html'), (200, 'ok')),
    ('pdf', ('file:test/resources/documents/sample.pdf', '3', 'd003', 'base64', 'application/pdf'),(200, 'ok')),
    ('jpg', ('file:test/resources/documents/sample.jpg', '4', 'd004', 'base64', 'image/jpeg'),(200, 'ok')),
    ('m4v', ('file:test/resources/documents/sample.m4v', '5', 'd005', 'base64', 'video/mp4'),(200, 'ok')),
    ('mp3', ('file:test/resources/documents/sample.mp3', '6', 'd006', 'base64', 'audio/mpeg'),(200, 'ok'))
    ]
)
def test_encodings(cleanup, client, test_case, input, expected):
    assert submit_inline_doc(client, input) == expected, test_case

@pytest.mark.parametrize("test_case, input, expected", [
    ('virus', ('file:test/resources/documents/eicar.txt', '1', 'v001', None, 'text/plain'), (400, 'Virus check failed on file'))])
def test_virus(cleanup, client, test_case, input, expected):
    result = submit_inline_doc(client, input)
    assert expected[0] == result[0] and result[1].startswith(expected[1]), test_case 