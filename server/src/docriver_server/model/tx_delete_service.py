import logging
from opentelemetry import trace

from dao.tx import create_tx, create_tx_event
from dao.document import get_doc_by_name, create_doc_event
from exceptions import ValidationException
from model.common import current_time_ms, format_result_base
from model.authorizer import authorize_delete
from trace_util import instrumented_connection

def delete_docs_tx(token, realm, payload, connection_pool, public_keys, audience):
    span = trace.get_current_span()
    span.set_attribute('realm', realm)
    metrics_attribs = {'realm': realm, 'txType': 'delete'}
    
    start = current_time_ms()
    payload['dr:realm'] = realm
    authorize_delete(public_keys, token, audience, payload)

    logging.info("Received deletion request: {}/{}. Principal: {}".format(payload['dr:realm'], payload['tx'], payload['dr:principal']))
    span.set_attributes({'principal': payload['dr:principal'], 'tx': payload['tx'],  'tx': payload['tx']})

    connection = instrumented_connection(connection_pool.get_connection())
    cursor = None
    try:
        cursor = connection.cursor()
        tx_id = create_tx(payload, 'delete', cursor)
        payload['dr:txId'] = tx_id    
        create_tx_event(cursor, tx_id)
        documents = payload['documents']
        for document in documents:
            doc_id, version_id, doc_status = get_doc_by_name(cursor, payload['dr:realm'], document['document']) 
            if doc_id == None or doc_status in ['R', 'D']:
                raise ValidationException('Document does not exist or has already been deleted/replaced')
            create_doc_event(cursor, tx_id, doc_id, None, 'DELETE', 'D')
        end = current_time_ms()
        result = format_result_base(start, payload, end)
        connection.commit()
        span.set_attributes({'numDocuments': len(documents), 'txKey': payload['dr:txId']})
        return result
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()