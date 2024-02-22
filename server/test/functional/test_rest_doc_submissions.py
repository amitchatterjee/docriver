import os
import shutil
import pytest
import json
from controller.http import init_app, init_params
from main import init_db, init_obj_store, init_virus_scanner

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
    return init_db('localhost', 3306, 'docriver', 'docriver', 'docriver', 2)

@pytest.fixture(scope="session", autouse=True)
def minio():
    return init_obj_store('localhost:9000', 'docriver-key', 'docriver-secret')

@pytest.fixture(scope="session", autouse=True)
def scanner():
    return init_virus_scanner('127.0.0.1', 3310)

@pytest.fixture(scope="session", autouse=True)
def client(connection_pool, minio, scanner):
    print("I am here 1")
    raw='../target/volumes/raw'
    rmmkdir(raw)

    untrusted = '../target/volumes/untrusted'
    rmmkdir(untrusted)

    app = init_app()
    app.config['TESTING'] = True
    init_params(connection_pool, minio, scanner, 'docriver', untrusted, raw, '/scandir')

    with app.test_client() as client:
        yield client

@pytest.fixture()
def cleanup(connection_pool, minio):
    print("I am here 2")
    connection = connection_pool.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute('DELETE FROM TX')
        cursor.execute('DELETE FROM DOC')
        connection.commit()

        delete_obj_recursively(minio, 'docriver', 'p123456')
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def test_health(cleanup, client):
    result = client.get('/health')
    assert json.loads(result.data)['system'] == 'UP'
