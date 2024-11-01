def get_health(bucket, connection_pool, minio, scanner):
    db_healthy = db_healthcheck(connection_pool)
    minio_healthy = minio.bucket_exists(bucket)
    scanner_healthy = scanner.ping() == "PONG"
    healthy_overall = db_healthy and minio_healthy and scanner_healthy
    return {'system': health_status(healthy_overall), 
            'db': health_status(db_healthy), 
            'minio': health_status(minio_healthy), 
            'scanner': health_status(scanner_healthy)}

def db_healthcheck(connection_pool):
    connection = connection_pool.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(('SELECT 1 FROM DUAL'))
        cursor.fetchone()
        return True
    except Exception:
        return False
    finally:
        cursor.close()
        connection.close()

def health_status(up):
    return "UP" if up else "DOWN"