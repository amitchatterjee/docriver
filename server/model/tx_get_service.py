from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from datetime import datetime

import dao.tx as dao

def get_events(realm, start, end, connection_pool, token, auth_public_keys, auth_audience):
    span = trace.get_current_span()
    span.set_attributes({'realm': realm, 
                        'startTime': start, 
                        'endTime': end})
    connection = connection_pool.get_connection()
    cursor = None
    try:
        cursor = connection.cursor()
        events = dao.get_events(cursor, realm, datetime.fromtimestamp(start), datetime.fromtimestamp(end))
        result = []
        for event in events:
            result.append({'eventTime': int(event[0].strftime('%s')),
                           'document': event[1],
                           'status': event[2],
                           'location': event[5],
                           'type': event[6],
                           'mime': event[7]})
        span.set_attribute('numEvents', len(events))
        span.set_status(Status(StatusCode.OK))
        return result
    except Exception as e:
        span.set_status(Status(StatusCode.ERROR))
        span.record_exception(e)
        raise e
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()