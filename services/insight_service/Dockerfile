# Build from the repo root: docker build -f services/insight_service/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY libs/common /libs/common
COPY services/insight_service /app

RUN pip install --no-cache-dir -e /libs/common -e .

EXPOSE 8003
CMD ["uvicorn", "insight_service.main:app", "--host", "0.0.0.0", "--port", "8003"]
