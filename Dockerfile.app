FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY setup.py .
COPY respirasp/ respirasp/

RUN pip install --no-cache-dir -e .

ENV MODEL_TARGET=local

CMD streamlit run respirasp/interface/app.py \
    --server.port ${PORT:-8080} \
    --server.address 0.0.0.0 \
    --server.headless true
