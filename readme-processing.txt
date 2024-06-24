#######################
# One-time setup
#######################
mkdir -p $HOME/airflow

# Add to $HOME/.bashrc
# Change this to the UID of the user who created the directory above
export AIRFLOW_UID=1000