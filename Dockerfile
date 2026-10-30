# Online deployment image (Railway or any Docker host).
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

# Uses the trained model in model/ (replace it online with Model Performance >
# Upload Trained Model; on Railway the upload is kept on the volume).
CMD ["sh", "deploy/start.sh"]
