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

def create_doc(cursor, document, realm):
    cursor.execute(("""
                    INSERT INTO DOC (DOCUMENT, REALM) 
                    VALUES (%s, %s)
                    """), 
                    (document['document'], realm))
    return cursor.lastrowid

def create_doc_version(bucket, cursor, tx_id, doc_id, doc_key, document):
    cursor.execute(("""
                    INSERT INTO DOC_VERSION (DOC_ID, TX_ID, LOCATION_URL, TYPE, MIME_TYPE)
                    VALUES(%s, %s, %s, %s, %s)
                    """), 
                    (doc_id, tx_id, "s3://{}/{}".format(bucket, doc_key),  
                    document['type'], 
                    document['content']['mimeType']))
    return cursor.lastrowid

def create_doc_event(cursor, tx_id, doc_id, replaces_doc_id, event_description, status):
    cursor.execute(("""
                    INSERT INTO DOC_EVENT (DESCRIPTION, STATUS, DOC_ID, REF_DOC_ID, REF_TX_ID) 
                    VALUES(%s, %s, %s, %s, %s) 
                    """), 
                    (event_description, status, doc_id, replaces_doc_id, tx_id))
    return cursor.lastrowid
    
def get_doc_by_name(cursor, realm, name):
    cursor.execute("""
        SELECT d.ID,
            MAX(v.ID) AS VERSION_ID,
            (SELECT MAX(e.ID) FROM DOC_EVENT e WHERE e.DOC_ID = d.ID GROUP BY e.DOC_ID) AS EVENT_ID,
            (SELECT e2.STATUS FROM DOC_EVENT e2 WHERE e2.ID = EVENT_ID) AS STATUS
        FROM DOC d, DOC_VERSION v
        WHERE
            d.ID = v.DOC_ID
            AND d.DOCUMENT = %(name)s
            AND d.REALM = %(realm)s
        GROUP BY d.ID
        """, 
        {"name": name, "realm": realm})
    row = cursor.fetchone()
    if row:
        return row[0], row[1], row[3]
    return (None, None, None)
