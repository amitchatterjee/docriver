import os
import pytest
import logging
import base64
from controller.http import init_app, init_params
from main import init_db, init_obj_store, init_virus_scanner

TEST_REALM = 'test123456'

def raw_dir():
    return os.path.abspath(os.path.join(os.getenv('DOCRIVER_GW_HOME'), 'server/test/resources/documents'))

def untrusted_dir():
    return os.getenv('DOCRIVER_UNTRUSTED_ROOT')

def delete_obj_recursively(minio, bucketname, folder):
    objs = minio.list_objects(bucketname, prefix=folder, recursive=True)
    for obj in objs:
        minio.remove_object(bucketname, obj.object_name)

def to_base64(filename):
    with open(filename, "rb") as file:
        inline = base64.b64encode(file.read())
    return inline.decode('utf-8')

def inline_doc(inline, tx, doc, encoding, mime_type, replaces):
    # saved_args = locals()
    # print("args:", saved_args)
    if inline.startswith('file:'):
        filename = inline[inline.find(':')+1:]
        full_path = os.path.join(raw_dir(), TEST_REALM ,filename)
        if encoding == 'base64':            
            inline = to_base64(full_path)
        else:
            with open(full_path, "r") as file:
                inline = file.read()
    # print(inline)
    payload = {
        'tx': tx,
        'realm': TEST_REALM,
        'documents': [
            {
                'document': doc,
                'type': 'sample',
                'content': {
                    'mimeType': mime_type,
                    'encoding': encoding,
                    'inline': inline
                }
            }
        ]
    }
    if replaces:
        payload['documents'][0]['replaces'] = replaces
    return payload

def submit_inline_doc(client, parameters, replaces=None):
    response = client.post('/tx', json=inline_doc(*parameters, replaces),
                           headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8')

def path_doc(path, tx, doc, mime_type):
    return {
        'tx': tx,
        'realm': TEST_REALM,
        'documents': [
            {
                'document': doc,
                'type': 'sample',
                'content': {
                    'mimeType': mime_type,
                    'path': path
                }
            }
        ]
    }

def submit_path_doc(client, parameters):
    response = client.post('/tx', json=path_doc(*parameters),
        headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8')

def path_docs(tx, doc_prefix, exclude = None):
    tx = {
        'tx': tx,
        'realm': TEST_REALM,
        'documents': []
    }
    for i, file in enumerate(os.listdir(os.path.join(raw_dir(), TEST_REALM))):
        if exclude and file == exclude:
            continue
        tx['documents'].append({
                'document': doc_prefix + str(i),
                'type': 'sample',
                'content': {
                    'path': file
                }
            })
    return tx

def submit_path_docs(client, tx, doc_prefix, exclude=None):
    message=path_docs(tx, doc_prefix, exclude)
    response = client.post('/tx', json=message,
        headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8'), message

def ref_doc(tx, doc):
    # saved_args = locals()
    # print("args:", saved_args)
    return {
        'tx': tx,
        'realm': TEST_REALM,
        'documents': [
            {
                'document': doc,
                'type': 'sample'
            }
        ]
    }

def submit_ref_doc(client, parameters):
    response = client.post('/tx', json=ref_doc(*parameters),
                           headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8')

def assert_location(minio, location):
    splits = location.split(':')
    assert 3 == len(splits)
    assert 'minio' == splits[0]
    assert 'docriver'== splits[1]
    iter = minio.list_objects('docriver', prefix=splits[2])
    count = 0
    for obj in iter:
        count = count + 1
    assert 1 == count

def exec_get_events(cursor, doc):
    cursor.execute("""
            SELECT e.STATUS, e.DESCRIPTION, e.REF_DOC_ID 
            FROM DOC_EVENT e, DOC d
            WHERE e.DOC_ID = d.ID
                AND d.DOCUMENT = %(doc)s
            ORDER BY e.ID
        """, {'doc': doc})