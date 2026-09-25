#!/bin/bash
# Monitor ngrok and update current URL file. Run as systemd service.
# Parses ngrok's output to detect URL changes.

URL_FILE="/home/opc/techlens/current_ngrok_url.txt"
LOG_FILE="/home/opc/techlens/ngrok-monitor.log"
NGROK_LOG="/tmp/ngrok.log"

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
    # Extract ngrok public URL from ngrok's output log
    # Look for "Forwarding" line with https URL
    if [ -f "$NGROK_LOG" ]; then
        CURRENT_URL=$(grep "Forwarding" "$NGROK_LOG" | grep -oP 'https://[^/\s]+' | head -1)
    else
        CURRENT_URL=""
    fi

    # Fallback: try to get from ngrok API (port 4040 or 4041)
    if [ -z "$CURRENT_URL" ]; then
        CURRENT_URL=$(timeout 2 curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | grep -oP '"public_url":"\K[^"]+' | head -1)
    fi
    if [ -z "$CURRENT_URL" ]; then
        CURRENT_URL=$(timeout 2 curl -s http://127.0.0.1:4041/api/tunnels 2>/dev/null | grep -oP '"public_url":"\K[^"]+' | head -1)
    fi

    # If no URL found, wait and retry
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
