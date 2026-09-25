#!/bin/bash
# Monitor ngrok and update current URL file. Run as systemd service.
# Queries ngrok's local API every 5 seconds to detect URL changes.

NGROK_API="http://localhost:4040/api/tunnels"
URL_FILE="/home/opc/techlens/current_ngrok_url.txt"
LOG_FILE="/home/opc/techlens/ngrok-monitor.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Initialize URL file if it doesn't exist
if [ ! -f "$URL_FILE" ]; then
    echo "http://localhost:8000" > "$URL_FILE"
    log "Initialized $URL_FILE"
fi

LAST_URL=$(cat "$URL_FILE")

while true; do
    # Query ngrok API for current public URL
    CURRENT_URL=$(curl -s "$NGROK_API" 2>/dev/null | grep -oP '"public_url":"\K[^"]+' | head -1)

    # If curl fails or ngrok not responding, wait and retry
    if [ -z "$CURRENT_URL" ]; then
        sleep 5
        continue
    fi

    # If URL changed, update the file
    if [ "$CURRENT_URL" != "$LAST_URL" ]; then
        echo "$CURRENT_URL" > "$URL_FILE"
        log "Updated ngrok URL: $CURRENT_URL"
        LAST_URL="$CURRENT_URL"
    fi

    sleep 5
done
