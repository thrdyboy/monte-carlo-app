FROM apache/airflow:2.9.2-python3.11

USER airflow

# Install Python deps
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Bake the DAGs and source code into the image
COPY --chown=airflow:root dags            /opt/airflow/dags
COPY --chown=airflow:root src             /opt/airflow/src

# Optional: local-only helper, harmless to include
COPY --chown=airflow:root generate_mock_data.py /opt/airflow/generate_mock_data.py

# Airflow expects these dirs to exist
RUN mkdir -p /opt/airflow/logs /opt/airflow/plugins