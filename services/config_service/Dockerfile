# Build from the repo root: docker build -f services/config_service/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY libs/common /libs/common
COPY services/config_service /app

RUN pip install --no-cache-dir -e /libs/common -e .

EXPOSE 8002
CMD ["uvicorn", "config_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
