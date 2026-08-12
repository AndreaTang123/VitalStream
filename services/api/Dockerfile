# Build from the repo root: docker build -f services/api/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY libs/common /libs/common
COPY services/api /app

RUN pip install --no-cache-dir -e /libs/common -e .

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
