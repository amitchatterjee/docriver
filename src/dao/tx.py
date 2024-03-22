
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