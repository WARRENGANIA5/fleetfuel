#!/bin/sh
# Container startup
set -e
cd /app

# Store backups and the uploaded model on the persistent volume
# (RAILWAY_VOLUME_MOUNT_PATH on Railway, PERSIST_DIR on Render).
# Without one, they're lost on redeploy.
PERSIST_DIR="${PERSIST_DIR:-$RAILWAY_VOLUME_MOUNT_PATH}"
if [ -n "$PERSIST_DIR" ]; then
    mkdir -p "$PERSIST_DIR/backups"
    rm -rf backups
    ln -s "$PERSIST_DIR/backups" backups
    # copy the bundled model on first run, keep uploads after that
    mkdir -p "$PERSIST_DIR/model"
    for f in linear_regression_pipeline.joblib metrics.json; do
        [ -f "$PERSIST_DIR/model/$f" ] || cp "model/$f" "$PERSIST_DIR/model/$f"
    done
    export MODEL_STORE="$PERSIST_DIR/model"
fi

# give the database a few seconds to come up
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
