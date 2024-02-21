
def create_tx(payload, cursor):
    cursor.execute(("INSERT INTO TX (TX, REALM) VALUES (%s, %s)"), (payload['tx'], 
                    payload['realm']))
    tx_id = cursor.lastrowid
    return tx_id

def create_tx_event(cursor, tx_id):
    cursor.execute(("""INSERT INTO TX_EVENT (EVENT, STATUS, TX_ID) 
                  VALUES(%s, %s, %s) 
                  """), 
                  ('INGESTION', 'I', tx_id))