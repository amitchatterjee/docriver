import pytest
import sys
import os

from test.functional.fixture import cleanup, client, connection_pool, minio, scanner, auth_keystore, client_with_security
from test.functional.util import submit_inline_doc, TEST_REALM, issuer_keystore_path, delete_docs

def test_notoken(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'))
    assert (401,'Not authorized for this operation') == result[0:2]

def test_successful_auth_using_realm_issued_token(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
                keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit'})
    assert (200,'ok') == result[0:2]

def test_submit_with_invalid_tx_type(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
        keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'delete'})
    assert (401,'Not authorized for this operation') == result[0:2]

def test_token_expired(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
        keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit'}, expires=1, delay=2)
    assert (401,'Not authorized for this operation') == result[0:2]

def test_wrong_issuer(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
        keystore_file=issuer_keystore_path('p123456'), permissions={'txType': 'submit'})
    assert (401,'Not authorized for this operation') == result[0:2]

def test_imposter(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
        keystore_file=issuer_keystore_path('docriver-imposter'), permissions={'txType': 'submit'})
    assert (401,'Not authorized for this operation') == result[0:2]

def test_no_resourcetype_reference(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
        keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit', 'resourceType': 't1-bill'})
    assert (401,'Not authorized for this operation') == result[0:2]

def test_bad_resourcetype_reference(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
        keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit', 'resourceType': 't1-bill'},
        tx_references=[{'resourceType':'t1-claim', 'resourceId': 't1', 'description': 't1 test description'}])
    assert (401,'Not authorized for this operation') == result[0:2]

def test_bad_resourceid_reference(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
        keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit', 'resourceType': 't1-claim', 'resourceId': 'xy'},
        tx_references=[{'resourceType':'t1-claim', 'resourceId': 't1', 'description': 't1 test description'}])
    assert (401,'Not authorized for this operation') == result[0:2]

def test_successful_reference(cleanup, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'),
        keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit', 'resourceType': '.*-claim', 'resourceId': 't.*'},
        tx_references=[{'resourceType':'t1-claim', 'resourceId': 't1', 'description': 't1 test description'}])
    assert (200,'ok') == result[0:2]

def test_successful_delete(cleanup, connection_pool, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'), keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit'})
    assert (200,'ok') == result
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '2', 'd002', 'base64', 'application/pdf'), keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit'})
    assert (200,'ok') == result
    result = delete_docs(client_with_security, '3', ['d001', 'd002'], keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'delete', 'document': 'd00(1|2)'})
    assert (200,'ok') == result[0:2]

def test_delete_with_more_files_than_authorized(cleanup, connection_pool, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'), keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit'})
    assert (200,'ok') == result
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '2', 'd002', 'base64', 'application/pdf'), keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit'})
    assert (200,'ok') == result
    result = delete_docs(client_with_security, '3', ['d001', 'd002'], keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'delete', 'document': 'd001'})
    assert (401,'Not authorized for this operation') == result[0:2]

def test_delete_with_invalid_tx_type(cleanup, connection_pool, client_with_security):
    result = submit_inline_doc(client_with_security, ('file:sample.pdf', '1', 'd001', 'base64', 'application/pdf'), keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit'})
    assert (200,'ok') == result
    result = delete_docs(client_with_security, '3', ['d001'], keystore_file=issuer_keystore_path(TEST_REALM), permissions={'txType': 'submit', 'document': 'd001'})
    assert (401,'Not authorized for this operation') == result[0:2]

# TODO - add test for reference authorization