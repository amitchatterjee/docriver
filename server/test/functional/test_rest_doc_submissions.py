import pytest

from test.functional.fixture import cleanup, client, connection_pool, minio, scanner
from test.functional.util import submit_inline_doc, submit_path_doc, submit_path_docs

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
    assert submit_inline_doc(client, input) == expected, test_case

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
    assert submit_path_doc(client, input) == expected, test_case

def test_multi_docs_submission_with_virus(cleanup, client):
    result = submit_path_docs(client, '1', 'doc-')
    assert result[0] == 400
    assert result[1].startswith('Virus check failed on file')

def test_multi_docs_submission(cleanup, client):
    assert submit_path_docs(client, '1', 'doc-', exclude='eicar.txt') == (200, 'ok')
    