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
    global submit_reqs_hist
    global submit_docs_hist
    global submit_error_hist
    
    meter = metrics.get_meter('docriver-gateway')
    
    # meter.create_observable_gauge(callbacks=[get_cpu_usage_callback], name="cpu_percent", description="CPU Utilization", unit="1")
    # meter.create_observable_gauge(callbacks=[get_ram_usage_callback], name="ram_percent", description="RAM Usage", unit="1")
    
    submit_reqs_hist = meter.create_histogram(name="drg_sub_reqs", description="number of submit requests", unit="1")
    submit_docs_hist = meter.create_histogram(name="drg_sub_docs", description="number of documents submitted in a transaction", unit="1")
    submit_error_hist = meter.create_histogram(name="drg_sub_errs", description="number of errors processing submit requests", unit="1")
    
def increment_submit_requests(attributes = {}):
   submit_reqs_hist.record(1, attributes)
   
def record_submit_size(size, attributes={}):
    submit_docs_hist.record(size, attributes)
    
def increment_submit_errors(attributes = {}):
   submit_error_hist.record(1, attributes)
