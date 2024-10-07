import psutil

import opentelemetry.metrics as metrics
from opentelemetry.metrics import Observation, CallbackOptions

def get_cpu_usage_callback(_: CallbackOptions):
    for (number, percent) in enumerate(psutil.cpu_percent(percpu=True)):
        attributes = {"cpu_number": str(number)}
        yield Observation(percent, attributes)

# Callback to gather RAM memory usage
def get_ram_usage_callback(_: CallbackOptions):
    ram_percent = psutil.virtual_memory().percent
    yield Observation(ram_percent)

def init_measurements():
    global requests_counter
    global submit_size_hist
    global proc_error_counter
    
    meter = metrics.get_meter('docriver-gateway')
    meter.create_observable_gauge(callbacks=[get_cpu_usage_callback], name="cpu_percent", description="CPU Utilization", unit="1")
    meter.create_observable_gauge(callbacks=[get_ram_usage_callback], name="ram_percent", description="RAM Usage", unit="1")
    
    requests_counter = meter.create_counter(name="requests", description="number of requests", unit="1")
    submit_size_hist = meter.create_histogram(name="submit_size_documents", description="number of documents received in a transaction", unit="1")
    proc_error_counter = meter.create_histogram(name="proc_error", description="processing_errors", unit="1")
    
def increment_requests(attributes = {}):
   requests_counter.add(1, attributes)
   
def record_submit_size(size, attributes={}):
    submit_size_hist.record(size, attributes)
    
def increment_errors(attributes = {}):
   proc_error_counter.record(1, attributes)
