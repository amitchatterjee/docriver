# Bring up the observer docker processes
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-observer.yml -p docriver up

# Override the following variable. Use "oltp" as the value. Or add to ~/.bashrc along with the rest of the opentel params
export DOCRIVER_OTEL_TRACE_EXP=otlp

# Start the gateway using docker compose

# Upload some documents
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug submit --source $HOME/few-cheetahs --documentType "Flickr images" --prefix "$(date '+%Y-%m-%d-%H-%M-%S')/" --resourceType image --resourceId 123 --resourceDescription 'upload from flickr'

# Trigger the tracing for getEvents:
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io get events

# Trigger the tracing for getDocument. NOTE: change the --name to an actual document name
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelTraceExp $DOCRIVER_OTEL_TRACE_EXP --otelTraceExpEndpoint http://localhost:4318/v1/traces --otelTraceAuthTokenKey $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER --otelTraceAuthTokenVal $DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug get document --name "2024-09-30-12-20-55/52946576006_420234d4f2_c.jpg-1727713256"

# View if you see the traces on opentel-collector console - for debugging:
http://localhost:55679/debug/tracez