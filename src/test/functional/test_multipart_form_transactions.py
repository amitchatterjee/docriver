import pytest

from test.functional.fixture import cleanup, client, connection_pool, minio, scanner
from test.functional.util import submit_multipart_docs

def test_multipart_files_submission_no_manifest(cleanup, client):
    result = submit_multipart_docs(client, '1', ['sample.jpg', 'sample.pdf'])
    assert (200,'ok') == result[0:2]

def test_multipart_files_submission_with_manifest(cleanup, client):
    # TODO
    pass