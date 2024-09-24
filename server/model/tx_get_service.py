from opentelemetry import trace, baggage
from opentelemetry.trace import Status, StatusCode
from opentelemetry.context import attach, detach
from datetime import datetime
from trace_util import new_span
from opentelemetry.instrumentation.mysql import MySQLInstrumentor

import dao.tx as dao

def get_events(realm, start, end, connection_pool, token, auth_public_keys, auth_audience):
    # token = attach(baggage.set_baggage('realm', realm))
    span = trace.get_current_span()
    span.set_attributes({'realm': realm, 'from': start, 
                        'to': end})
    
    # TODO authorize the request
    
    connection = MySQLInstrumentor().instrument_connection(connection_pool.get_connection())
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