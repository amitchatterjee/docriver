import pytest
import sys
import os

from test.functional.fixture import cleanup, client, connection_pool, minio, scanner
from test.functional.util import submit_multipart_docs

def test_multipart_files_submission(cleanup, client):
    result = submit_multipart_docs(client, '1', ['sample.jpg', 'sample.pdf'])
    assert (200,'ok') == result[0:2]