import pytest

from test.functional.fixture import cleanup, client, connection_pool, minio, scanner
from test.functional.util import submit_inline_doc, submit_path_doc, submit_path_docs, assert_location

def test_health(client):
    response = client.get('/health')
    assert response.json['system'] == 'UP'

# The parameters are (test_name, (inline_text, tx, document, encoding, mime_type), (expected_http_status, expected_dr_status))
@pytest.mark.parametrize("test_case, input, expected", [
    ('plain text', ('Hello world', '1', 'd001', None, 'text/plain'), (200, 'ok')),
    ('html', ('<body><b>Hello world</b></body>', '2', 'd002', None, 'text/html'), (200, 'ok')),
    ('pdf', ('file:sample.pdf', '3', 'd003', 'base64', 'application/pdf'),(200, 'ok')),
    ('jpg', ('file:sample.jpg', '4', 'd004', 'base64', 'image/jpeg'),(200, 'ok')),
    ('m4v', ('file:sample.m4v', '5', 'd005', 'base64', 'video/mp4'),(200, 'ok')),
    ('mp3', ('file:sample.mp3', '6', 'd006', 'base64', 'audio/mpeg'),(200, 'ok'))
    ]
)
def test_inline_document_submission(cleanup, client, test_case, input, expected):
    assert expected == submit_inline_doc(client, input), test_case

@pytest.mark.parametrize("test_case, input, expected", [
    ('virus', ('file:eicar.txt', '1', 'v001', None, 'text/plain'), (400, 'Virus check failed on file'))])
def test_document_with_virus(cleanup, client, test_case, input, expected):
    result = submit_inline_doc(client, input)
    assert expected[0] == result[0] and result[1].startswith(expected[1]), test_case

# The parameters are (test_name, (inline_text, tx, document, mime_type), (expected_http_status, expected_dr_status))
@pytest.mark.parametrize("test_case, input, expected", [
    ('pdf', ('sample.pdf', '1', 'p001', 'application/pdf'),(200, 'ok')),
    ('jpg', ('sample.jpg', '2', 'p002', 'image/jpeg'),(200, 'ok')),
    ('m4v', ('sample.m4v', '3', 'p003', 'video/mp4'),(200, 'ok')),
    ('mp3', ('sample.mp3', '4', 'p004', 'audio/mpeg'),(200, 'ok'))
    ]
)
def test_path_document_submission(cleanup, client, test_case, input, expected):
    assert expected == submit_path_doc(client, input), test_case

def test_multi_docs_submission_with_virus(cleanup, client):
    result = submit_path_docs(client, '1', 'doc-')
    assert 400 == result[0]
    assert result[1].startswith('Virus check failed on file')

def test_multi_docs_submission(cleanup, client):
    assert 200, 'ok' == submit_path_docs(client, '1', 'doc-', exclude='eicar.txt')[0:2]

def test_db_and_storage_after_submission_success(cleanup, connection_pool, minio, client):
    result = submit_path_docs(client, '1', 'doc-', exclude='eicar.txt')
    assert 200, 'ok' == result[0:2]
    response = result[2]

    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("""
                SELECT t.TX, d.DOCUMENT, d.TYPE, d.MIME_TYPE,
                       v.LOCATION_URL, e.STATUS, e.DESCRIPTION, e.REF_DOC_ID
                FROM TX t, DOC d, DOC_VERSION v, DOC_EVENT e
                WHERE
                    d.ID = v.DOC_ID
                    AND v.TX_ID = t.ID
                    AND e.DOC_ID = d.ID
                    AND e.REF_TX_ID = t.ID
                ORDER BY DOCUMENT
            """)
        response['documents'].sort(key=lambda doc: doc['document'])
        for i, row in enumerate(cursor):
            assert row[0] == response['tx'], 'tx value mismatch'
            assert row[1] == response['documents'][i]['document'], 'document name mismatch'
            assert row[2] == response['documents'][i]['type'], 'document type mismatch'
            # assert row[3] == response['documents'][i]['mimeType'], 'document mimetype mismatch'
            assert 'I' == row[5]
            assert 'INGESTION' == row[6]
            assert not row[7]
            assert_location(minio, row[4])
        assert cursor.rowcount == len(response['documents'])
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()