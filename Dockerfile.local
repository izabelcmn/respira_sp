FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install package
COPY setup.py .
COPY respira_sp/ respira_sp/
RUN pip install --no-cache-dir -e .

# Environment variables
ENV MODEL_TARGET=local
ENV RESPIRA_API_URL=http://localhost:8000

# Expose ports
EXPOSE 8000 8501

# Start both API and Streamlit in the same container
CMD uvicorn respira_sp.api.fast:app --host 0.0.0.0 --port 8000 & \
    sleep 3 && \
    streamlit run respira_sp/interface/app.py \
        --server.port 8501 \
        --server.address 0.0.0.0 \
        --server.headless true
