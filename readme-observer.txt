# Bring up the observer docker processes
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-observer.yml -p docriver up

# Override the following variable. Use "oltp" as the value
export DOCRIVER_OTEL_EXP=otlp

# Start the gateway using docker compose

# Upload some documents - this is only needed if you have not uploaded any documents in the last day or so. Alternatively, you can modify the curl command, below, to specify a start and end URL parameter. The start and end times are in epoch time
bulk-docs-submit.sh -f $HOME/cheetah -y "Flickr images" -e "$(date '+%Y-%m-%d-%H-%M-%S')/" -u "https://localhost:8443/tx" -n

# To trigger the tracing:
curl --insecure --header "Accept: application/json"  https://localhost:8443/tx/p123456


# View if you see the traces on opentel-collector console:
http://localhost:55679/debug/tracez