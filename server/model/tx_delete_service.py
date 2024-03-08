from dao.tx import create_tx, create_tx_event
from dao.document import get_doc_by_name, create_doc_event
from exceptions import ValidationException
from model.common import current_time_ms, format_result_base

def delete_docs_tx(payload, connection_pool):
    start = current_time_ms()
    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        tx_id = create_tx(payload, cursor)
        payload['dr:txId'] = tx_id
        create_tx_event(cursor, tx_id)
        
        documents = payload['documents']
        for document in documents:
            doc_id, version_id, doc_status = get_doc_by_name(cursor, document['document']) 
            if doc_id == None or doc_status in ['R', 'D']:
                raise ValidationException('Document does not exist or has already been deleted/replaced')
            create_doc_event(cursor, tx_id, doc_id, None, 'DELETE', 'D')
        end = current_time_ms()
        result = format_result_base(start, payload, end)
        connection.commit()
        return result
    except Exception as e:
        connection.rollback()
        raise e
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()