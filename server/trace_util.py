from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace import set_span_in_context
from opentelemetry.context import get_current
from contextlib import contextmanager

@contextmanager
def new_span(name, **kwargs):
    tracer = trace.get_tracer('docriver-gateway')
    with tracer.start_as_current_span(name, **kwargs) as span:
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            raise e