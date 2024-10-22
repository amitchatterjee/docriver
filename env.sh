export DOCRIVER_GW_HOME=$HOME/git/docriver-gateway
export DOCRIVER_UNTRUSTED_ROOT=$HOME/storage/docriver/untrusted

export DOCRIVER_MYSQL_USER=docriver
export DOCRIVER_MYSQL_PASSWORD=docriver
export DOCRIVER_MYSQL_ROOT_PASSWORD=docriver
export DOCRIVER_MYSQL_HOST=127.0.0.1
export DOCRIVER_MYSQL_PORT=3306
export DOCRIVER_MYSQL_VERSION=8.2

export DOCRIVER_MINIO_VERSION=RELEASE.2023-12-23T07-19-11Z.fips
export DOCRIVER_MINIO_CONSOLE_PORT=9001
export DOCRIVER_MINIO_PORT=9000

export DOCRIVER_CLAMAV_VERSION=stable_base
export DOCRIVER_CLAMAV_PORT=3310

export DOCRIVER_NGINX_VERSION=latest
export DOCRIVER_NGINX_PORT=8443

export EXAMPLE_APP_NGINX_PORT=443

export DOCRIVER_OPENTEL_GRPC_PORT=4317
export DOCRIVER_OPENTEL_HTTP_PORT=4318
export DOCRIVER_OPENTEL_UX_PORT=55679

# Change the following environment variable to "otlp" if you want to use the opentelemetry collector. You can also set the value to "console" to view the traces on console. Note that when using "otlp", the observer docker processes must be started - see below
export DOCRIVER_OTEL_TRACE_EXP=none

# These parameters are used by the collector to export the traces.
export DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT=http://opentel-collector:${DOCRIVER_OPENTEL_HTTP_PORT}/v1/traces
export DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_HEADER=
export DOCRIVER_OTEL_TRACE_EXPORT_ENDPOINT_AUTH_VAL=

# Change the following environment variable to "otlp" if you want to use the opentelemetry collector. You can also set the value to "console" to view the metrics on console. Note that when using "otlp", the observer docker processes must be started - see below
export DOCRIVER_OTEL_METRICS_EXP=none

# These parameters are used by the collector to export the traces. They must be set when using the observer
export DOCRIVER_OTEL_METRICS_EXPORT_ENDPOINT=http://opentel-collector:${DOCRIVER_OPENTEL_HTTP_PORT}/v1/metrics
export DOCRIVER_OTEL_METRICS_EXPORT_ENDPOINT_AUTH_HEADER=docriver-gateway
export DOCRIVER_OTEL_METRICS_EXPORT_ENDPOINT_AUTH_VAL=


# Change the following environment variable to --otelLogInstrument  if you want to instrument the logs opentelemetry trace information.
export DOCRIVER_OTEL_LOG_INSTRUMENT=--no-otelLogInstrument

# These parameters are used by the collector to export the traces. They must be set when using the observer
export DOCRIVER_OTEL_LOG_EXPORT_ENDPOINT=http://opentel-collector:${DOCRIVER_OPENTEL_HTTP_PORT}/v1/logs
export DOCRIVER_OTEL_LOG_EXPORT_ENDPOINT_AUTH_HEADER=docriver-gateway
export DOCRIVER_OTEL_LOG_EXPORT_ENDPOINT_AUTH_VAL=

export DOCRIVER_OTEL_CONNECTION_INSTRUMENT=--otelConnectionInstrument

# Make changes as needed. Many of these settings will need to match with the OIDC and proxy settings. Example - 
# OIDC/OAUTH2 settings:
# export DOCRIVER_OIDC_CLIENTID="XXXXXX"
# export DOCRIVER_OIDC_SECRET="YYYYYY"
# export DOCRIVER_OIDC_DISCOVERY_URL="https://dev-XXXXX.okta.com/oauth2/default/.well-known/openid-configuration"
# export DOCRIVER_OIDC_REDIRECT_URL="https://gateway.quik-j.com/redirect"
# export DOCRIVER_AUTH_URL="https://dev-XXXXXX.okta.com/oauth2/default"
# export DOCRIVER_OIDC_POST_LOGOUT_REDIRECT_URL="https://gateway.quik-j.com"
# Proxy settings:
# export DOCRIVER_MINIO_CONSOLE_URL="https://docriver.quik-j.com/minio/console"

export DOCRIVER_OIDC_CLIENTID=
export DOCRIVER_OIDC_SECRET=
export DOCRIVER_OIDC_DISCOVERY_URL=
export DOCRIVER_OIDC_REDIRECT_URL=
export DOCRIVER_AUTH_URL=
export DOCRIVER_MINIO_CONSOLE_URL=

export PATH=$PATH:$DOCRIVER_GW_HOME/infrastructure/sh:$DOCRIVER_GW_HOME/client/sh:$DOCRIVER_GW_HOME/server:$DOCRIVER_GW_HOME/client/python
