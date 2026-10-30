#!/bin/sh
# Container start-up for the online deployment.
set -e
cd /app

# Keep the database backups on the persistent disk, so they survive redeploys:
# Railway sets RAILWAY_VOLUME_MOUNT_PATH when a volume is attached; on Render
# (paid plans only) set PERSIST_DIR to the disk's mount path. Without either,
# backups and an uploaded model last until the next restart or redeploy.
PERSIST_DIR="${PERSIST_DIR:-$RAILWAY_VOLUME_MOUNT_PATH}"
if [ -n "$PERSIST_DIR" ]; then
    mkdir -p "$PERSIST_DIR/backups"
    rm -rf backups
    ln -s "$PERSIST_DIR/backups" backups
    # The model also lives on the disk: start from the one in the image,
    # then keep whatever is uploaded from Google Colab.
    mkdir -p "$PERSIST_DIR/model"
    for f in linear_regression_pipeline.joblib metrics.json; do
        [ -f "$PERSIST_DIR/model/$f" ] || cp "model/$f" "$PERSIST_DIR/model/$f"
    done
    export MODEL_STORE="$PERSIST_DIR/model"
fi

# The database service can take a few seconds longer to start than this one.
tries=0
until python init_db.py; do
    tries=$((tries + 1))
    if [ "$tries" -ge 20 ]; then
        echo " * Could not reach the database. Check FIREBASE_CREDENTIALS_JSON."
        exit 1
    fi
    echo " * Waiting for the database..."
    sleep 3
done

exec python app.py
