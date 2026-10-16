# Online deployment image (Railway or any Docker host).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Manila \
    ONLINE=1

# mariadb-client provides mysqldump for the automatic backups; tzdata for Philippine time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends mariadb-client tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-train.txt ./
RUN pip install --no-cache-dir -r requirements-train.txt

COPY . .

# The model is trained on this server's own data when it starts.
CMD ["sh", "deploy/start.sh"]
