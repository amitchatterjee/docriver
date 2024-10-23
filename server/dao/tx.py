
def create_tx(payload, tx_type, cursor):
    cursor.execute(("INSERT INTO TX (TX, TX_TYPE, REALM, PRINCIPAL) VALUES (%s, %s, %s, %s)"), 
                   (payload['tx'], tx_type, payload['dr:realm'], payload['dr:principal']))
    tx_id = cursor.lastrowid
    return tx_id

def create_tx_event(cursor, tx_id):
    cursor.execute(("""INSERT INTO TX_EVENT (EVENT, STATUS, TX_ID) 
                  VALUES(%s, %s, %s) 
                  """), 
                  ('INGESTION', 'I', tx_id))
    
def get_events(cursor, realm, start_time, end_time):
    cursor.execute("""SELECT 
        e.EVENT_TIME, d.DOCUMENT, e.STATUS, e.REF_TX_ID, e.REF_DOC_ID, v.LOCATION_URL, v.TYPE, v.MIME_TYPE
        FROM 
            DOC_EVENT e
            JOIN DOC d ON e.DOC_ID = d.ID
            JOIN DOC_VERSION v ON v.DOC_ID = d.ID
        WHERE 
            e.EVENT_TIME BETWEEN FROM_UNIXTIME(%s) AND FROM_UNIXTIME(%s)
            AND d.REALM = %s
        ORDER BY 
            e.EVENT_TIME
        """, (start_time, end_time, realm))
    # print(cursor.statement)
    events = []
    rows = cursor.fetchall()
    for row in rows:
        events.append((row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7]))
    return events
    # format_strings = ','.join(['%s'] * len(list_of_ids))
    # cursor.execute("DELETE FROM foo.bar WHERE baz IN (%s)" % format_strings,
    #            tuple(list_of_ids))