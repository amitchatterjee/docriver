import time

def current_time_ms():
    return round(time.time() * 1000)

def format_result_base(start, payload, end):
    result = {'dr:status': 'ok', 'dr:took': end - start}
    result.update(payload)
    return result