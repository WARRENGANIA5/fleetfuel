# Image for Railway / any Docker host
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Manila \
    ONLINE=1

# tzdata for Philippine time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-train.txt ./
RUN pip install --no-cache-dir -r requirements-train.txt

COPY . .

# Ships the model in model/; uploads go to the volume on Railway.
CMD ["sh", "deploy/start.sh"]
