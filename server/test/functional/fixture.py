import os
import pytest
import logging
from controller.http import init_app, init_params
from gateway import init_db, init_obj_store, init_virus_scanner, init_authorization, init_tracing, init_metrics
from test.functional.util import delete_obj_recursively, TEST_REALM, raw_dir, untrusted_dir, auth_keystore_path

@pytest.fixture(scope="session", autouse=True)
def connection_pool():
    return init_db(os.getenv('DOCRIVER_MYSQL_HOST', default='127.0.0.1'), 
                   os.getenv('DOCRIVER_MYSQL_PORT', default=3306), 
                   os.getenv('DOCRIVER_MYSQL_USER', default='docriver'), 
                   os.getenv('DOCRIVER_MYSQL_PASSWORD', default='docriver'), 
                   'docriver', 5)

@pytest.fixture(scope="session", autouse=True)
def auth_keystore():
    store = init_authorization(auth_keystore_path(), 'docriver')
    return store

@pytest.fixture(scope="session", autouse=True)
def minio():
    return init_obj_store('localhost:9000', 'docriver-key', 'docriver-secret')

@pytest.fixture(scope="session", autouse=True)
def scanner():
    return init_virus_scanner('127.0.0.1', 3310)

@pytest.fixture(scope="session", autouse=True)
def tracer():
    return init_tracing()

@pytest.fixture(scope="session", autouse=True)
def metrics():
    return init_metrics()

@pytest.fixture(scope="session", autouse=True)
def client(connection_pool, minio, scanner, tracer, metrics):
    app = core_client(connection_pool, minio, scanner, tracer, metrics, None, None, None, None, None, None)
    with app.test_client() as client:
        yield client

@pytest.fixture(scope="session", autouse=True)
def client_with_security(connection_pool, minio, scanner, tracer, metrics, auth_keystore):
    app = core_client(connection_pool, minio, scanner, tracer, metrics, *auth_keystore, 'docriver')
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

def core_client(connection_pool, minio, scanner, tracer, metrics, auth_private_key, auth_public_key, auth_signer_cert, auth_signer_cn, auth_public_keys, auth_audience):
    logging.basicConfig(level='INFO')
    app = init_app()
    app.config['TESTING'] = True
    init_params(connection_pool, minio, scanner, 'docriver', untrusted_dir(), raw_dir(), '/scandir', auth_private_key, auth_public_key, auth_signer_cert, auth_signer_cn, auth_public_keys, auth_audience)
    return app