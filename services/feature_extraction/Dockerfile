# Build from the repo root: docker build -f services/feature_extraction/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY libs/common /libs/common
COPY services/feature_extraction /app

RUN pip install --no-cache-dir -e /libs/common -e .

CMD ["python", "-m", "feature_extraction.main"]
