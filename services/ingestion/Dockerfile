# Build from the repo root: docker build -f services/ingestion/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY libs/common /libs/common
COPY services/ingestion /app

RUN pip install --no-cache-dir -e /libs/common -e .

EXPOSE 8001
CMD ["python", "-m", "ingestion.run"]
