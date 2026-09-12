FROM python:3.11-slim

WORKDIR /app

# System deps for psycopg2 and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the API code
COPY api /app/api
# Copy the shared src/ so the API can reuse loaders, config, and schemas
COPY src /app/src

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]