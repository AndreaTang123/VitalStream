# Build from the repo root: docker build -f services/device_simulator/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY libs/common /libs/common
COPY services/device_simulator /app

RUN pip install --no-cache-dir -e /libs/common -e .

CMD ["python", "-m", "device_simulator.replay", "--subject", "S2"]
