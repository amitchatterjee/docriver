# Bring up the observer docker processes
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-observer.yml -p docriver up

# Override the following variable. Use "oltp" as the value. Or add to ~/.bashrc along with the rest of the opentel params
export DOCRIVER_OTEL_EXP=otlp

# Start the gateway using docker compose

# Upload some documents - this is only needed if you have not uploaded any documents in the last day or so. Alternatively, you can modify the curl command, below, to specify a start and end URL parameter. The start and end times are in epoch time
bulk-docs-submit.sh -f $HOME/few-cheetahs -y "Flickr images" -e "$(date '+%Y-%m-%d-%H-%M-%S')/" -u "https://localhost:8443/tx" -n

# To trigger the tracing for getEvents:
# TODO remove hardcoding for the endpoint
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelExp $DOCRIVER_OTEL_EXP --otelExpEndpoint http://localhost:4318/v1/traces --otelAuthTokenKey $DOCRIVER_OPENTEL_EXPORT_ENDPOINT_AUTH_HEADER --otelAuthTokenVal $DOCRIVER_OPENTEL_EXPORT_ENDPOINT_AUTH_VAL get events

# To trigger the tracing for getDocument:
drc.py --realm p123456 --docriverUrl https://localhost:8443 --noverify --otelExp $DOCRIVER_OTEL_EXP --otelExpEndpoint http://localhost:4318/v1/traces --otelAuthTokenKey $DOCRIVER_OPENTEL_EXPORT_ENDPOINT_AUTH_HEADER --otelAuthTokenVal $DOCRIVER_OPENTEL_EXPORT_ENDPOINT_AUTH_VAL --keystore $HOME/.ssh/docriver/docriver.p12 --keystorePassword 'docriver' --subject collector@docriver.io --debug get document --name 58be1ca0-7a9d-11ef-98f3-2016b95ee0b1 --output /tmp/something.pdf

# To trigger the tracing for document submit using REST:
doc-submit.sh -m 'application/pdf' -y payment-receipt -r claim -i C1234567 -p "Proof of payment" -m application/pdf -f $DOCRIVER_GW_HOME/server/test/resources/documents/test123456/sample.pdf -u "https://localhost:8443/tx" -n

# To triger tracing for submit form:
bulk-docs-submit.sh -f $HOME/few-cheetahs -y "Flickr images" -e "$(date '+%Y-%m-%d-%H-%M-%S')/" -u "https://localhost:8443/tx" -n

# View if you see the traces on opentel-collector console - for debugging:
http://localhost:55679/debug/tracez