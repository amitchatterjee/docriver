import pytest

from test.functional.fixture import cleanup, client, connection_pool, minio, scanner, tracer
from test.functional.util import submit_multipart_docs

def test_multipart_files_submission_no_manifest(cleanup, client):
    result = submit_multipart_docs(client, '1', ['sample.jpg', 'sample.pdf'])
    assert (200,'ok') == result[0:2]

def test_multipart_files_submission_with_manifest(cleanup, client):
    result = submit_multipart_docs(client, '1', ['manifest.json', 'sample.jpg', 'sample.pdf'])
    assert (200,'ok') == result[0:2]

def test_multipart_files_submission_html_output(cleanup, client):
    result = submit_multipart_docs(client, '1', ['sample.jpg', 'sample.pdf'], accept='text/html')
    assert 200 == result[0]
    # TODO parse the HTML and verify
    # print(result)