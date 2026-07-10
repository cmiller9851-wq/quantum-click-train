FROM python:3.12-slim

WORKDIR /app

# Emplace internal layout structure
COPY src/ /app/src/
COPY config/ /app/config/

# Ensure stderr logs are flushed in real-time for logging backends
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "src/cra_quantum_mesh.py"]
