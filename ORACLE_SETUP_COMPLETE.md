# TechLens Complete Setup for Oracle Cloud

Fresh setup guide from scratch.

## Prerequisites

Assume you have:
- Oracle Cloud VM (Always Free tier)
- SSH access as `opc` user
- Docker installed
- ngrok installed and authenticated

## Step 1: Clone/Update Repository

```bash
cd /home/opc
git clone https://github.com/kirthistaank/techlens.git
# OR if already cloned:
cd /home/opc/techlens
git pull origin main
```

## Step 2: Setup Environment Variables

Create `.env` file with your configuration:

```bash
cat > /home/opc/techlens/.env << 'EOF'
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:14b
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_NUM_CTX=8192
OLLAMA_TEMPERATURE=0.1

# Database
DATABASE_URL=sqlite:///./techlens.db

# Email (optional for demo)
SMTP_USER=
SMTP_PASSWORD=

# App
LOG_LEVEL=INFO
PIPELINE_SCHEDULE_HOUR=6

# Demo configuration
DEMO_ACCESS_ENABLED=true
TOKEN_EXPIRY_HOURS=24
NGROK_URL=http://localhost:8000
EOF
```

**Important:** Don't set `NGROK_URL` to the actual URL—the monitor script updates it automatically.

## Step 3: Start Backend Container

```bash
cd /home/opc/techlens

# Build and start
docker-compose down  # Clean slate
docker-compose up -d

# Verify it's running
docker-compose ps
docker-compose logs -f techlens
```

Wait for logs to show "TechLens started", then Ctrl+C.

## Step 4: Kill Any Stale ngrok Instances

```bash
pkill -f "ngrok http" || true
sleep 2
ps aux | grep ngrok  # Should show no ngrok processes
```

## Step 5: Start Fresh ngrok Instance

```bash
# Start ngrok in background
ngrok http 8000 > /tmp/ngrok.log 2>&1 &

# Wait for it to start
sleep 3

# Check it's running
ps aux | grep "ngrok http" | grep -v grep

# Extract the public URL
NGROK_URL=$(grep "Forwarding" /tmp/ngrok.log | grep -oP 'https://[^/\s]+' | head -1)
echo "ngrok URL: $NGROK_URL"
```

If the URL doesn't show, check the log:
```bash
cat /tmp/ngrok.log
```

## Step 6: Verify Backend Works

Test the API:

```bash
# Test health
curl http://localhost:8000/api/digest/daily

# Test config endpoint (will show localhost until monitor updates it)
curl http://localhost:8000/api/config
```

This might return localhost for now:
```json
{"ngrok_url":"http://localhost:8000"}
```

The monitor service (Step 7) will update this with the real ngrok URL

## Step 7: Setup ngrok Monitoring

Make the script executable:

```bash
chmod +x /home/opc/techlens/manage-ngrok.sh
```

Copy the systemd service:

```bash
sudo cp /home/opc/techlens/ngrok-monitor.service /etc/systemd/system/
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ngrok-monitor
sudo systemctl start ngrok-monitor
```

## Step 8: Verify Monitor is Working

Check status:

```bash
sudo systemctl status ngrok-monitor
```

Check logs:

```bash
tail -20 /home/opc/techlens/ngrok-monitor.log
```

Wait 10 seconds, then check if URL was updated:

```bash
cat /home/opc/techlens/current_ngrok_url.txt
```

Should show the actual ngrok URL (like `https://unwired-gear-glowing.ngrok-free.dev`).

## Step 9: Test API Config Endpoint

```bash
curl http://localhost:8000/api/config
```

Should return:
```json
{"ngrok_url":"https://unwired-gear-glowing.ngrok-free.dev"}
```

## Step 10: Test Demo Form

Access from GitHub Pages with your ngrok URL:

```
https://kirthistaank.github.io/join-demo.html?backend=https://YOUR-NGROK-URL.ngrok-free.dev
```

Replace `YOUR-NGROK-URL` with the one from step 5.

1. Enter name and email
2. Click "Join Demo"
3. Should redirect to the app with a token

## Debugging Checklist

If something doesn't work:

```bash
# Check ngrok is running with ONE instance
ps aux | grep "ngrok http" | grep -v grep

# Check backend is running
docker-compose ps
docker-compose logs --tail=20 techlens

# Check monitor is running
sudo systemctl status ngrok-monitor
tail -50 /home/opc/techlens/ngrok-monitor.log

# Check current URL file
cat /home/opc/techlens/current_ngrok_url.txt

# Test ngrok API (might timeout but that's ok)
timeout 3 curl http://127.0.0.1:4040/api/tunnels || echo "API not responding (expected)"

# Check ports
netstat -tulnp | grep -E "8000|4040"
```

## If ngrok Crashes

The systemd service will auto-restart it. Check:

```bash
sudo systemctl status ngrok-monitor
journalctl -u ngrok-monitor -f
```

The monitor detects the new URL within 5 seconds and updates the file.

## Quick Restart All

If you need a complete fresh restart:

```bash
# Kill ngrok
pkill -f "ngrok http"

# Stop everything
docker-compose down

# Start fresh
docker-compose up -d
ngrok http 8000 > /tmp/ngrok.log 2>&1 &
sleep 3

# Monitor should auto-update the URL
sleep 5
cat /home/opc/techlens/current_ngrok_url.txt
```
