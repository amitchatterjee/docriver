from opentelemetry import trace
from datetime import datetime

import logging

import dao.tx as dao
from model.authorizer import authorize_get_events
from trace_util import instrumented_connection

def get_events(realm, start, end, connection_pool, token, public_keys, audience):
    # token = attach(baggage.set_baggage('realm', realm))
    span = trace.get_current_span()
    span.set_attributes({'realm': realm, 'from': start, 
                        'to': end})
    principal,auth,issuer = authorize_get_events(public_keys, token, audience, realm)    
    logging.info("Received tx events for: {}. Principal: {}".format(realm, principal))
    span.set_attribute('principal', principal)
    
    connection = instrumented_connection(connection_pool.get_connection())
    cursor = None
    try:
        cursor = connection.cursor()
        events = dao.get_events(cursor, realm, start, end)
        result = []
        for event in events:
            result.append({'eventTime': int(event[0].strftime('%s')),
                           'document': event[1],
                           'status': event[2],
                           'location': event[5],
                           'type': event[6],
                           'mime': event[7]})
        span.set_attribute('numEvents', len(events))
        return result
    finally:
        if cursor:
            cursor.close()
        if connection.is_connected():
            connection.close()