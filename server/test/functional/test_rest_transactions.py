import pytest
import sys
import os
import time

from test.functional.fixture import cleanup, client, connection_pool, minio, scanner, tracer, metrics
from test.functional.util import submit_inline_doc, submit_path_doc, submit_path_docs, assert_location, exec_get_events, submit_ref_doc, delete_docs, TEST_REALM

def test_health(client):
    response = client.get('/health')
    assert 'UP' == response.json['system']

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
def test_inline_doc_submission(cleanup, client, test_case, input, expected):
    assert expected == submit_inline_doc(client, input), test_case

@pytest.mark.parametrize("test_case, input, expected", [
    ('virus', ('file:eicar.txt', '1', 'v001', None, 'text/plain'), (400, 'Virus check failed on file'))])
def test_infected_doc_submission(cleanup, client, test_case, input, expected):
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
def test_path_doc_submission(cleanup, client, test_case, input, expected):
    assert expected == submit_path_doc(client, input), test_case

def test_infected_multi_docs_submission(cleanup, client):
    result = submit_path_docs(client, '1', 'doc-')
    assert 400 == result[0]
    assert result[1].startswith('Virus check failed on file')

def test_multi_docs_submission(cleanup, client):
    assert (200, 'ok') == submit_path_docs(client, '1', 'doc-', excludes=['eicar.txt', 'manifest.json'])[0:2]

def test_db_and_storage_after_submission_success(cleanup, connection_pool, minio, client):
    result = submit_path_docs(client, '1', 'doc-', excludes=['eicar.txt', 'manifest.json'])
    assert (200, 'ok') == result[0:2]
    response = result[2]

    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("""
                SELECT t.TX, t.TX_TYPE, d.DOCUMENT, d.REALM,
                       v.TYPE, v.MIME_TYPE, v.LOCATION_URL, e.STATUS, e.DESCRIPTION, e.REF_DOC_ID
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
            assert 'submit' == row[1]
            assert row[2] == response['documents'][i]['document'], 'document name mismatch'
            assert TEST_REALM == row[3]
            assert row[4] == response['documents'][i]['type'], 'document type mismatch'
            # assert row[5] == response['documents'][i]['mimeType'], 'document mimetype mismatch'
            assert 'I' == row[7]
            assert 'INGESTION' == row[8]
            assert not row[9]
            assert_location(minio, row[6])
        assert cursor.rowcount == len(response['documents'])
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def test_doc_replacement(cleanup, connection_pool, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.pdf', '2', 'd002', 'base64', 'application/pdf'), replaces='d001')
    assert (200,'ok') == result
    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("""
                SELECT d.ID, d.DOCUMENT
                FROM DOC d
                WHERE d.DOCUMENT = %(doc)s 
            """,
        {'doc': 'd002'})
        count = 0
        for id, document, in cursor:
            assert 'd002' == document
            count = count+1
        assert count == 1

        exec_get_events(cursor, 'd001')
        rows = []
        for row in cursor:
            rows.append(row)
        assert 2 == len(rows)
        assert rows[0] == ('I', 'INGESTION', None)
        assert rows[1][0:2] == ('R', 'REPLACEMENT')
        assert rows[1][2] != None

        exec_get_events(cursor, 'd002')
        rows = []
        for row in cursor:
            rows.append(row)
        assert 1 == len(rows)
        assert rows[0] == ('I', 'INGESTION', None)
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()


def test_new_version(cleanup, connection_pool, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.pdf', '2', 'd001', 'base64', 'application/pdf'), replaces='d001')
    assert (200,'ok') == result 
    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("""
                SELECT d.ID, d.DOCUMENT
                FROM DOC d
                WHERE d.DOCUMENT = %(doc)s 
            """,
        {'doc': 'd001'})
        count = 0
        for id, document in cursor:
            assert 'd001' == document
            count = count+1
        assert count == 1
        
        exec_get_events(cursor, 'd001')
        rows = []
        for row in cursor:
            rows.append(row)
        assert [('I', 'INGESTION', None), ('V', 'NEW_VERSION', None), ('I', 'INGESTION', None)] == rows

        cursor.execute("""
                SELECT LOCATION_URL
                FROM DOC_VERSION
                ORDER BY ID 
            """)
        count = 0
        for row in cursor:
            count = count+1
        assert 2 == count
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()
   
def test_ref_doc(cleanup, connection_pool, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_ref_doc(client, ('2', 'd001'))
    assert (200,'ok') == result
    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("""
                SELECT LOCATION_URL
                FROM DOC_VERSION
                ORDER BY ID 
            """)
        count = 0
        for row in cursor:
            count = count+1
        assert 1 == count

        exec_get_events(cursor, 'd001')
        rows = []
        for row in cursor:
            rows.append(row)
        assert [('I', 'INGESTION', None), ('J', 'REFERENCE', None)] == rows
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def test_doc_with_replaced_ref(cleanup, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.pdf', '2', 'd002', 'base64', 'application/pdf'), replaces='d001')
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.pdf', '3', 'd003', 'base64', 'application/pdf'), replaces='d001')
    assert 400 == result[0]

def test_new_doc_after_doc_replacement(cleanup, connection_pool, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.pdf', '2', 'd002', 'base64', 'application/pdf'), replaces='d001')
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.pdf', '3', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("""
                SELECT d.DOCUMENT, e.STATUS
                FROM DOC d, DOC_EVENT e
                WHERE e.DOC_ID = d.ID
                ORDER BY d.ID; 
            """)
        rows = []
        for row in cursor:
            rows.append(row)
        assert [('d001', 'I'), ('d001', 'R'), ('d001', 'I'), ('d002', 'I')] == rows

        cursor.execute("""
                SELECT v.LOCATION_URL
                FROM DOC d, DOC_VERSION v
                WHERE v.DOC_ID = d.ID
                    AND d.DOCUMENT = %(doc)s; 
            """, {'doc': 'd001'})
        count = 0
        for row in cursor:
            count = count+1
        assert 2 == count
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()
            
def test_document_delete(cleanup, connection_pool, client):
    connection = connection_pool.get_connection()
    cursor = None
    try:
        result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
        assert (200,'ok') == result
        result = submit_inline_doc(client, ('file:sample.pdf', '2', 'd002', 'base64', 'application/pdf'))
        assert (200,'ok') == result
        result = delete_docs(client, '3', ['d001', 'd002'])
        assert (200,'ok') == result[0:2]
        
        cursor = connection.cursor()
        assert_doc_event(cursor, 'd001', [('I', 'INGESTION', None), ('D', 'DELETE', None)])
        assert_doc_event(cursor, 'd002', [('I', 'INGESTION', None), ('D', 'DELETE', None)])
        cursor.close()
        connection.close()

        result = submit_inline_doc(client, ('file:sample.pdf', '4', 'd001', 'base64', 'application/pdf'))
        assert (200,'ok') == result
        connection = connection_pool.get_connection()
        cursor = connection.cursor()
        assert_doc_event(cursor, 'd001', [('I', 'INGESTION', None), ('D', 'DELETE', None), ('I', 'INGESTION', None)])
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def test_document_delete_failed(cleanup, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.pdf', '2', 'd002', 'base64', 'application/pdf'), replaces='d001')
    assert (200,'ok') == result

    result = delete_docs(client, '3', ['d001'])
    assert 400 == result[0]
    assert 'Document does not exist or has already been deleted/replaced' == result[1]

    result = delete_docs(client, '4', ['d002'])
    assert (200,'ok') == result[0:2]
    result = delete_docs(client, '5', ['d002'])
    assert 400 == result[0]
    assert 'Document does not exist or has already been deleted/replaced' == result[1]

def test_references(cleanup, client, connection_pool):
    assert (200, 'ok') == submit_path_docs(client, '1', 'doc-', excludes=['eicar.txt', 'manifest.json'],
                            tx_references=[{'resourceType':'t1-claim', 'resourceId': 't1', 'description': 't1 test description', 'properties': {'tk11': 'tv11', 'tk12': 'tv12'}},
                            {'resourceType':'t2-claim', 'resourceId': 't2', 'description': 't2 test description', 'properties': {'tk21': 'tv21', 'tk22': 'tv22'}}],
                            doc_references={
                                'sample.jpg': [{'resourceType':'d1-claim', 'resourceId': 'd1', 'description': 'd1 test description', 'properties': {'dk11': 'dv11', 'dk12': 'dv12'}},
                            {'resourceType':'d2-claim', 'resourceId': 'd2', 'description': 'd2 test description', 'properties': {'dk21': 'dv21', 'dk22': 'dv22'}}]})[0:2]
    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT d.DOCUMENT, r.RESOURCE_TYPE, r.RESOURCE_ID, r.DESCRIPTION, p.KEY_NAME, p.VALUE
            FROM DOC d, DOC_VERSION v, DOC_REF r, DOC_REF_PROPERTY p
            WHERE v.DOC_ID = d.ID
                AND r.DOC_VERSION_ID = v.ID
                AND p.REF_ID = r.ID
            ORDER BY d.DOCUMENT, r.RESOURCE_TYPE, r.RESOURCE_ID, p.KEY_NAME
        """)
        expected = [
            ("doc-1","d1-claim","d1","d1 test description","dk11","dv11"),
            ("doc-1","d1-claim","d1","d1 test description","dk12","dv12"),
            ("doc-1","d2-claim","d2","d2 test description","dk21","dv21"),
            ("doc-1","d2-claim","d2","d2 test description","dk22","dv22"),
            ("doc-1","t1-claim","t1","t1 test description","tk11","tv11"),
            ("doc-1","t1-claim","t1","t1 test description","tk12","tv12"),
            ("doc-1","t2-claim","t2","t2 test description","tk21","tv21"),
            ("doc-1","t2-claim","t2","t2 test description","tk22","tv22"),
            ("doc-2","t1-claim","t1","t1 test description","tk11","tv11"),
            ("doc-2","t1-claim","t1","t1 test description","tk12","tv12"),
            ("doc-2","t2-claim","t2","t2 test description","tk21","tv21"),
            ("doc-2","t2-claim","t2","t2 test description","tk22","tv22"),
            ("doc-3","t1-claim","t1","t1 test description","tk11","tv11"),
            ("doc-3","t1-claim","t1","t1 test description","tk12","tv12"),
            ("doc-3","t2-claim","t2","t2 test description","tk21","tv21"),
            ("doc-3","t2-claim","t2","t2 test description","tk22","tv22"),
            ("doc-4","t1-claim","t1","t1 test description","tk11","tv11"),
            ("doc-4","t1-claim","t1","t1 test description","tk12","tv12"),
            ("doc-4","t2-claim","t2","t2 test description","tk21","tv21"),
            ("doc-4","t2-claim","t2","t2 test description","tk22","tv22")
        ]
        index = 0
        for row in cursor:
            assert expected[index] == row
            index = index+1
        assert len(expected) == index
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()

def assert_doc_event(cursor, doc, events):
    exec_get_events(cursor, doc)
    rows = []
    for row in cursor:
        rows.append(row)
    assert len(events) == len(rows)
    assert events == rows

def test_document_successful_get(cleanup, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result

    response = client.get('/document/' + TEST_REALM + '/d001')
    assert 200 == response.status_code
    # with open("/tmp/d001.pdf", "wb") as f:
    #     f.write(response.data)

def test_document_get_failed_already_deleted(cleanup, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = delete_docs(client, '2', ['d001'])
    assert (200,'ok') == result[0:2]

    response = client.get('/document/' + TEST_REALM + '/d001')
    assert 404 == response.status_code

def test_document_get_failed_replaced(cleanup, connection_pool, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.pdf', '2', 'd002', 'base64', 'application/pdf'), replaces='d001')
    assert (200,'ok') == result

    response = client.get('/document/' + TEST_REALM + '/d001')
    assert 404 == response.status_code

def test_document_get_latest_version(cleanup, connection_pool, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.jpg', '2', 'd001', 'base64', 'image/jpeg'), replaces='d001')
    assert (200,'ok') == result
    response = client.get('/document/' + TEST_REALM + '/d001')
    assert 200 == response.status_code
    assert 'image/jpeg' == response.headers['Content-Type']
    
def test_document_get_events_default(cleanup, connection_pool, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.jpg', '2', 'd002', 'base64', 'image/jpeg'))
    assert (200,'ok') == result
    response = client.get(f"/tx/{TEST_REALM}", headers={"Accept": "application/json"})
    assert 200 == response.status_code
    json_result = response.json
    assert 2 == len(json_result)
    
def test_document_get_events_with_limits(cleanup, connection_pool, client):
    result = submit_inline_doc(client, ('file:sample.pdf', '1', 'd000', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    
    time.sleep(1)
    start = int(time.time())
    result = submit_inline_doc(client, ('file:sample.pdf', '2', 'd001', 'base64', 'application/pdf'))
    assert (200,'ok') == result
    result = submit_inline_doc(client, ('file:sample.jpg', '3', 'd002', 'base64', 'image/jpeg'))
    assert (200,'ok') == result
    time.sleep(1)
    end = int(time.time())
    
    response = client.get(f"/tx/{TEST_REALM}", query_string={'from': start, 'to': end}, headers={"Accept": "application/json"})
    assert 200 == response.status_code
    json_result = response.json
    assert 2 == len(json_result)