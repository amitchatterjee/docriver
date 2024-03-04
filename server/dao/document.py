def create_references(cursor, references, version_id):
    for reference in references:
        cursor.execute(("""
            INSERT INTO DOC_REF 
                (RESOURCE_TYPE, RESOURCE_ID, DESCRIPTION, DOC_VERSION_ID) 
            VALUES(%s, %s, %s, %s) 
            """), 
            (reference['resourceType'], 
            reference ['resourceId'],
            reference['description'] if 'description' in reference else None, 
            version_id))
        ref_id = cursor.lastrowid
        if 'properties' in reference:
            for k,v in reference['properties'].items():
                cursor.execute( ("""
                        INSERT INTO DOC_REF_PROPERTY 
                            (REF_ID, KEY_NAME, VALUE) 
                        VALUES(%s, %s, %s)
                        """), 
                        (ref_id, k, v))
    return ref_id

def create_doc(cursor, document):
    cursor.execute(("""
                    INSERT INTO DOC (DOCUMENT, TYPE, MIME_TYPE) 
                    VALUES (%s, %s, %s)
                    """), 
                    (document['document'],  
                    document['type'], 
                    document['content']['mimeType']))
    return cursor.lastrowid

def create_doc_version(bucket, cursor, tx_id, doc_id, doc_key):
    cursor.execute(("""
                    INSERT INTO DOC_VERSION (DOC_ID, TX_ID, LOCATION_URL)
                    VALUES(%s, %s, %s)
                    """), 
                    (doc_id, tx_id, "minio:{}:{}".format(bucket, doc_key)))
    return cursor.lastrowid

def create_doc_event(cursor, tx_id, doc_id, replaces_doc_id, event_description, status):
    cursor.execute(("""
                    INSERT INTO DOC_EVENT (DESCRIPTION, STATUS, DOC_ID, REF_DOC_ID, REF_TX_ID) 
                    VALUES(%s, %s, %s, %s, %s) 
                    """), 
                    (event_description, status, doc_id, replaces_doc_id, tx_id))
    return cursor.lastrowid

def get_doc_and_version_by_name(cursor, name):
    cursor.execute("""
                    SELECT MAX(v.ID) AS VERSION_ID, v.DOC_ID,
                        (SELECT MAX(e.ID) FROM DOC_EVENT e WHERE e.DOC_ID = d.ID GROUP BY e.DOC_ID) AS EVENT_ID,
                        (SELECT e2.STATUS FROM DOC_EVENT e2 WHERE e2.ID = EVENT_ID) AS STATUS
                    FROM DOC_VERSION v, DOC d
                    WHERE d.ID = v.DOC_ID 
                        AND d.DOCUMENT = %(doc)s 
                    GROUP BY DOC_ID
                    """, 
                    {'doc': name})
    row = cursor.fetchone()
    if row:
        return {
            'doc': row[1],
            'version': row[0],
            'status': row[3]
        }
    return None
    
def get_doc_by_name(cursor, name):
    cursor.execute("""
        SELECT d.ID,
            (SELECT MAX(e.ID) FROM DOC_EVENT e WHERE e.DOC_ID = d.ID GROUP BY e.DOC_ID) AS EVENT_ID,
            (SELECT e2.STATUS FROM DOC_EVENT e2 WHERE e2.ID = EVENT_ID) AS STATUS
        FROM DOC d
        WHERE
            d.DOCUMENT = %(name)s
        """, 
        {"name": name})
    row = cursor.fetchone()
    if row:
        return row[0], row[2]
    return None
