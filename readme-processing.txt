#######################
# Operations
#######################
pip install apache-airflow

#######################
# Operations
#######################
# Start airflow
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-airflow.yml -p docriver up -d

# Run command from CLI
docker compose -f $DOCRIVER_GW_HOME/infrastructure/compose/docker-compose-airflow.yml -p docriver run --rm  airflow-cli airflow dags  backfill hello-world --start-date 2015-06-01  --end-date 2015-06-07