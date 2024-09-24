from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace import set_span_in_context
from contextlib import contextmanager

@contextmanager
def new_span(name, **kwargs):
    span = None
    try:
        tracer = trace.get_tracer('docriver-gateway')
        parent = trace.get_current_span()
        context = set_span_in_context(parent)
        span = tracer.start_span(name, context=context, **kwargs) 
        yield span
        span.set_status(Status(StatusCode.OK))
    except Exception as e:
        span.set_status(Status(StatusCode.ERROR))
        span.record_exception(e)
        raise e
    finally:
        if span:
            span.end()