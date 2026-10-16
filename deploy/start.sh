#!/bin/sh
# Container start-up for the online deployment.
set -e
cd /app

# Keep uploaded profile photos and database backups on the persistent volume,
# so they survive redeploys (Railway sets RAILWAY_VOLUME_MOUNT_PATH when a
# volume is attached to the service).
if [ -n "$RAILWAY_VOLUME_MOUNT_PATH" ]; then
    mkdir -p "$RAILWAY_VOLUME_MOUNT_PATH/avatars" "$RAILWAY_VOLUME_MOUNT_PATH/backups"
    rm -rf static/images/avatars backups
    ln -s "$RAILWAY_VOLUME_MOUNT_PATH/avatars" static/images/avatars
    ln -s "$RAILWAY_VOLUME_MOUNT_PATH/backups" backups
fi

# The database service can take a few seconds longer to start than this one.
tries=0
until python init_db.py; do
    tries=$((tries + 1))
    if [ "$tries" -ge 20 ]; then
        echo " * Could not reach the database. Check the MYSQL* variables."
        exit 1
    fi
    echo " * Waiting for the database..."
    sleep 3
done

exec python app.py
