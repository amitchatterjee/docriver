import os
import pytest
import logging
from controller.http import init_app, init_params
from main import init_db, init_obj_store, init_virus_scanner
from test.functional.util import delete_obj_recursively, TEST_REALM

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
    raw='test/resources/documents'
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