import os
import base64
import time
from controller.http import init_app
from gateway import init_db, init_obj_store, init_virus_scanner
from docriver_auth.keystore import get_entries
from docriver_auth.auth_token import issue
from model.s3_url import parse_url
TEST_REALM = 'test123456'

def raw_dir():
    return os.path.abspath(os.path.join(os.getenv('DOCRIVER_GW_HOME'), 'server/test/resources/documents'))

def untrusted_dir():
    return os.getenv('DOCRIVER_UNTRUSTED_ROOT')

def auth_keystore_path():
    return os.path.abspath(os.path.join(os.getenv('DOCRIVER_GW_HOME'), 'server/test/resources/auth/truststore.p12'))

def issuer_keystore_path(issuer):
    return os.path.abspath(os.path.join(os.getenv('DOCRIVER_GW_HOME'), 
        "server/test/resources/auth/{}.p12".format(issuer)))

def delete_obj_recursively(minio, bucketname, folder):
    objs = minio.list_objects(bucketname, prefix=folder, recursive=True)
    for obj in objs:
        minio.remove_object(bucketname, obj.object_name)

def to_base64(filename):
    with open(filename, "rb") as file:
        inline = base64.b64encode(file.read())
    return inline.decode('utf-8')

def inline_doc_message(inline, tx, doc, encoding, mime_type, replaces, token, tx_references):
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
    if token:
        payload['authorization'] = token
    if replaces:
        payload['documents'][0]['replaces'] = replaces
    if tx_references:
        payload['references'] = tx_references
    return payload

def submit_inline_doc(client, parameters, replaces=None, keystore_file=None, permissions=None, expires=300, delay=0, tx_references=None):
    token = None
    if keystore_file:
        private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(keystore_file, 'docriver')
        encoded = issue(private_key, signer_cn, 'unknown', 'docriver', expires, 'docriver', permissions)
        token = "Bearer " + encoded[0]
        # print(encoded)
        if delay > 0:
            time.sleep(delay)
    response = client.post('/tx/' + TEST_REALM, 
                           json=inline_doc_message(*parameters, replaces, token, tx_references),
                           headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8')

def path_doc_message(path, tx, doc, mime_type):
    return {
        'tx': tx,
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
    response = client.post('/tx/' + TEST_REALM, json=path_doc_message(*parameters),
        headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8')

def path_docs_message(tx, doc_prefix, excludes=None, doc_references=None, tx_references=None):
    tx = {
        'tx': tx,
        'documents': []
    }
    if tx_references:
        tx['references'] = tx_references

    for i, file in enumerate(os.listdir(os.path.join(raw_dir(), TEST_REALM))):
        if excludes and file in excludes:
            continue
        document = {
                'document': doc_prefix + str(i),
                'type': 'sample',
                'content': {
                    'path': file
                }
            }
        if doc_references and file in doc_references:
            document['references'] = doc_references[file]

        tx['documents'].append(document)
    return tx

def submit_path_docs(client, tx, doc_prefix, excludes=['manifest.json'], doc_references=None, tx_references=None):
    message=path_docs_message(tx, doc_prefix, excludes, doc_references, tx_references)
    response = client.post('/tx/' + TEST_REALM, json=message,
        headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8'), message

def ref_doc_message(tx, doc):
    return {
        'tx': tx,
        'documents': [
            {
                'document': doc,
                'type': 'sample'
            }
        ]
    }

def submit_ref_doc(client, parameters):
    response = client.post('/tx/' + TEST_REALM, json=ref_doc_message(*parameters),
                           headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8')

def assert_location(minio, location):
    bucket,path = parse_url(location)
    assert 'docriver'== bucket
    iter = minio.list_objects(bucket, prefix=path)
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
    
def delete_docs(client, tx, docs, keystore_file=None, permissions=None, expires=300):
    token=None
    if keystore_file:
        private_key, public_key, signer_cert, signer_cn, public_keys = get_entries(keystore_file, 'docriver')
        encoded = issue(private_key, signer_cn, 'unknown', 'docriver', expires, 'docriver', permissions)
        token = "Bearer " + encoded[0]

    message=delete_docs_message(tx, docs, token=token)
    response = client.delete('/tx/' + TEST_REALM, json=message,
        headers={'Accept': 'application/json'})
    # print(response.status_code, response.data)
    return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8'), message

def delete_docs_message(tx, docs, token=None):
    payload =  {
        'tx': tx,
        'documents': [
        ]
    }

    if token:
        payload['authorization'] = token

    for doc in docs:
        payload['documents'].append({'document': doc}) 
    return payload

def submit_multipart_docs(client, tx, filenames, accept='application/json'):
    files = []
    for filename in filenames:
        files.append((open(os.path.join(raw_dir(), TEST_REALM , filename), "rb"), filename))
    response = client.post("/tx/" + TEST_REALM, data={
        'tx': tx,
        'files': files,
    }, headers={'Accept': accept})
    if accept == 'application/json':
        return response.status_code, response.json['dr:status'] if response.status_code == 200 else response.data.decode('utf-8'), response.json
    else:
        return response.status_code, response.data.decode('utf-8')    
