import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.getenv('DOCRIVER_GW_HOME'), 'server')))

from test.functional.fixture import cleanup, client, connection_pool, minio, scanner, auth_keystore, client_with_security
from test.functional.util import submit_inline_doc, TEST_REALM, issuer_keystore_path

def test_notoken(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (401,'Not authorized for this operation') == result[0:2]

def test_successful_auth_using_realm_issued_token(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
                keystore_file=issuer_keystore_path(TEST_REALM), permissions={'realm': TEST_REALM})
    assert (200,'ok') == result[0:2]

def test_token_expired(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
                keystore_file=issuer_keystore_path(TEST_REALM), permissions={'realm': TEST_REALM}, expires=1, delay=2)
    assert (401,'Not authorized for this operation') == result[0:2]

def test_wrong_issuer(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
                keystore_file=issuer_keystore_path('p123456'), permissions={'realm': TEST_REALM})
    assert (401,'Not authorized for this operation') == result[0:2]

def test_imposter(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
                keystore_file=issuer_keystore_path('docriver-imposter'), permissions={'realm': TEST_REALM})
    assert (401,'Not authorized for this operation') == result[0:2]