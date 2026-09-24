# ngrok Public Demo Setup for TechLens

## Problem Statement

When deploying TechLens to hiring managers for demo:

1. **Oracle Cloud IP is not memorable** — `129.146.58.128:8000` is hard to share and remember
2. **Public IP might change** — Ephemeral IPs on Oracle Cloud can change when instance restarts
3. **No HTTPS** — Browser shows "Not Secure" warning
4. **ngrok solves this but introduces a problem** — Each time ngrok restarts, it generates a **new random URL**
5. **Sharing becomes difficult** — You can't give hiring managers a static URL; you have to send them a new one each time

**Example:**
```
First startup:  https://abc123def456.ngrok.io
After restart:  https://xyz789uvw012.ngrok.io  ← Different!
```

---

## Solution: Auto-Update Landing Page

**Intention:** Create a system where:
1. ngrok generates a random HTTPS URL on startup
2. That URL is automatically captured and stored
3. Hiring managers visit a **static, memorable landing page** 
4. The landing page displays the current ngrok URL
5. Landing page redirects them to the live TechLens app
6. When TechLens restarts, the landing page automatically updates with the new URL

**How it helps:**
- ✅ You only share ONE URL with hiring managers: your landing page
- ✅ They always get the latest ngrok URL (even after restarts)
- ✅ Professional HTTPS (ngrok provides free SSL)
- ✅ No need to contact them with "Here's the new URL..."
- ✅ Looks polished and well-thought-out
- ✅ Free (no Cloudflare needed)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Hiring Manager                                          │
└────────────┬────────────────────────────────────────────┘
             │
             │ Visits (bookmarks this)
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│ Landing Page (Static HTML)                              │
│ https://your-landing-page.com/current-url.html          │
│ (or GitHub Pages / Simple file server)                  │
│                                                         │
│ Shows: "Current TechLens URL: https://abc123.ngrok.io" │
│ Auto-refreshes every 5 seconds                          │
└────────────┬────────────────────────────────────────────┘
             │
             │ Clicks link / redirects to
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│ ngrok (Public Tunnel)                                   │
│ https://abc123def456.ngrok.io ← Changes on restart     │
│          ↓                                              │
│ Oracle Cloud Instance (Port 8000)                       │
│          ↓                                              │
│ TechLens App (Frontend + API)                           │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

1. **ngrok account** (free at https://ngrok.com)
2. **ngrok auth token** (from dashboard)
3. **GitHub account** (for hosting landing page, OR use your Oracle instance)
4. **5-10 minutes** to set up

---

## Setup Instructions

### Step 1: Install ngrok

**On your Mac:**
```bash
brew install ngrok
```

**On Oracle Cloud Instance (SSH):**
```bash
# Download ngrok
curl -fsSL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz | tar xz

# Move to PATH
sudo mv ./ngrok /usr/local/bin/
```

**Verify installation:**
```bash
ngrok --version
# Should show: ngrok version X.X.X
```

### Step 2: Get ngrok Auth Token

1. Go to https://dashboard.ngrok.com/get-started
2. Sign up (free)
3. Copy your **Auth Token**
4. On your instance:
```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN_HERE
```

### Step 3: Start ngrok in Background

```bash
# SSH into Oracle instance
ssh -i ~/.ssh/your-key.key opc@129.146.58.128

# Start ngrok (runs in background)
nohup ngrok http 8000 > ngrok.log 2>&1 &

# Verify it's running
curl http://localhost:4040/api/tunnels
# Should return JSON with public_url
```

### Step 4: Create URL Capture Script

Create `scripts/capture_ngrok_url.sh` on your instance:

```bash
#!/bin/bash
# Capture current ngrok URL and save to file

NGROK_API="http://localhost:4040/api/tunnels"
OUTPUT_FILE="/home/opc/techlens/current_ngrok_url.txt"

# Wait for ngrok to be ready
sleep 3

# Get ngrok URL (retry up to 5 times)
for i in {1..5}; do
    NGROK_URL=$(curl -s $NGROK_API | grep -o '"public_url":"[^"]*' | grep -o 'https[^"]*' | head -1)
    if [ ! -z "$NGROK_URL" ]; then
        break
    fi
    sleep 2
done

if [ -z "$NGROK_URL" ]; then
    echo "ERROR: Could not get ngrok URL" >> /tmp/capture_ngrok.log
    exit 1
fi

# Save to file (also accessible via API)
echo "$NGROK_URL" > "$OUTPUT_FILE"
echo "✓ ngrok URL saved: $NGROK_URL" >> /tmp/capture_ngrok.log
echo "URL: $NGROK_URL"
```

Make it executable:
```bash
chmod +x scripts/capture_ngrok_url.sh
```

### Step 5: Add API Endpoint to TechLens

Edit `src/techlens/api/routes.py`:

```python
import os
from pathlib import Path

# Add this endpoint to your router
@router.get("/api/current-url")
def get_current_url():
    """
    Return the current public ngrok URL.
    Useful for demo/staging environments.
    """
    ngrok_url_file = Path("/home/opc/techlens/current_ngrok_url.txt")
    
    if ngrok_url_file.exists():
        current_url = ngrok_url_file.read_text().strip()
        return {
            "url": current_url,
            "status": "running",
            "app": "TechLens"
        }
    else:
        return {
            "url": "http://localhost:8000",
            "status": "local",
            "app": "TechLens",
            "note": "ngrok URL file not found, returning localhost"
        }
```

### Step 6: Create Landing Page

Create `frontend/public/current-url.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TechLens - Live Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 700px;
            padding: 50px 40px;
            text-align: center;
        }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 2.2em;
        }
        .status {
            display: inline-block;
            background: #d4edda;
            color: #155724;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            margin-bottom: 30px;
        }
        .url-box {
            background: #f8f9fa;
            border: 2px solid #667eea;
            border-radius: 8px;
            padding: 20px;
            margin: 30px 0;
        }
        .url-label {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
        }
        .url-text {
            font-family: monospace;
            font-size: 1.1em;
            color: #333;
            word-break: break-all;
            margin-bottom: 15px;
            min-height: 30px;
        }
        .loading {
            color: #999;
            font-style: italic;
        }
        .button {
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 14px 40px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            font-size: 1.1em;
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
            border: none;
        }
        .button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        .info {
            color: #666;
            font-size: 0.9em;
            margin-top: 30px;
            padding-top: 30px;
            border-top: 1px solid #eee;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 6px;
            margin: 20px 0;
            display: none;
        }
        .copy-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9em;
            margin-left: 10px;
        }
        .copy-btn:hover {
            background: #764ba2;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 TechLens</h1>
        <div class="status">✓ Live Demo Ready</div>
        
        <p style="color: #666; margin-bottom: 20px;">
            Local-first AI Tech Intelligence Agent
        </p>

        <div class="url-box">
            <div class="url-label">📡 Current Demo URL:</div>
            <div class="url-text" id="url-display">
                <span class="loading">Loading...</span>
            </div>
            <button class="copy-btn" onclick="copyURL()">Copy Link</button>
        </div>

        <button class="button" onclick="launchApp()" id="launch-btn" disabled>
            🚀 Launch TechLens
        </button>

        <div class="error" id="error-msg">
            ⚠️ Could not load demo URL. Please try again in a few seconds.
        </div>

        <div class="info">
            <p>💡 This page auto-updates every 5 seconds</p>
            <p style="margin-top: 10px; font-size: 0.8em; color: #999;">
                Bookmark this page to always get the latest demo URL
            </p>
        </div>
    </div>

    <script>
        let currentUrl = null;

        async function fetchCurrentUrl() {
            try {
                // Try to fetch from local API first
                const response = await fetch('/api/current-url');
                const data = await response.json();
                currentUrl = data.url;
                
                document.getElementById('url-display').innerHTML = `
                    <a href="${currentUrl}" target="_blank" style="color: #667eea; text-decoration: none;">
                        ${currentUrl}
                    </a>
                `;
                document.getElementById('launch-btn').disabled = false;
                document.getElementById('error-msg').style.display = 'none';
            } catch (error) {
                console.error('Error fetching URL:', error);
                document.getElementById('error-msg').style.display = 'block';
                document.getElementById('launch-btn').disabled = true;
                
                // Retry in 5 seconds
                setTimeout(fetchCurrentUrl, 5000);
            }
        }

        function launchApp() {
            if (currentUrl) {
                window.location.href = currentUrl;
            }
        }

        function copyURL() {
            if (currentUrl) {
                navigator.clipboard.writeText(currentUrl).then(() => {
                    alert('URL copied to clipboard!');
                });
            }
        }

        // Fetch URL on page load
        fetchCurrentUrl();

        // Refresh every 5 seconds
        setInterval(fetchCurrentUrl, 5000);
    </script>
</body>
</html>
```

### Step 7: Create Startup Script

Create `scripts/start_techlens_demo.sh`:

```bash
#!/bin/bash
# Complete startup script for TechLens demo environment

set -e

echo "🚀 Starting TechLens Demo..."

# Step 1: Start ngrok
echo "📡 Starting ngrok tunnel..."
nohup ngrok http 8000 > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!
echo "ngrok PID: $NGROK_PID"

# Step 2: Wait for ngrok to be ready
sleep 3

# Step 3: Capture ngrok URL
echo "📸 Capturing ngrok URL..."
./scripts/capture_ngrok_url.sh

# Step 4: Start Docker services
echo "🐳 Starting Docker services..."
docker compose up -d

# Step 5: Display info
echo ""
echo "════════════════════════════════════════════════════"
echo "✓ TechLens Demo is running!"
echo "════════════════════════════════════════════════════"
echo ""
echo "📄 Landing Page (share this with hiring managers):"
echo "   http://your-domain.com/current-url.html"
echo ""
echo "🔗 Ngrok URL (changes on restart):"
cat /home/opc/techlens/current_ngrok_url.txt
echo ""
echo "🌐 Local Access:"
echo "   http://localhost:8000"
echo ""
echo "📊 Monitor:"
echo "   Ngrok dashboard: http://localhost:4040"
echo "   Docker logs: docker compose logs -f"
echo ""
```

Make it executable:
```bash
chmod +x scripts/start_techlens_demo.sh
```

### Step 8: Host Landing Page

**Option A: GitHub Pages (Recommended)**

1. Create a simple GitHub repo: `techlens-demo`
2. Put `current-url.html` in repo
3. Enable GitHub Pages
4. Share: `https://your-github-username.github.io/techlens-demo/current-url.html`

**Option B: Serve from Oracle Instance**

Edit `src/techlens/api/main.py`:

```python
from fastapi.staticfiles import StaticFiles

# Serve static HTML files
app.mount("/demo", StaticFiles(directory="frontend/public", html=True), name="demo")
```

Then access: `http://129.146.58.128:8000/demo/current-url.html`

**Option C: Simple HTTP Server**

```bash
cd frontend/public
python -m http.server 8888

# Access: http://localhost:8888/current-url.html
```

---

## Full Workflow

### First Time Setup

```bash
# 1. Install ngrok
brew install ngrok
ngrok config add-authtoken YOUR_TOKEN

# 2. Clone/navigate to techlens
cd ~/techlens

# 3. Make scripts executable
chmod +x scripts/capture_ngrok_url.sh
chmod +x scripts/start_techlens_demo.sh

# 4. Update config and code (as shown above)
# - Add /api/current-url endpoint
# - Create current-url.html landing page

# 5. Rebuild Docker
docker compose build --no-cache techlens

# 6. Start everything
./scripts/start_techlens_demo.sh
```

### Daily Usage

```bash
# Start demo
./scripts/start_techlens_demo.sh

# Share landing page with hiring managers
# They bookmark it and always get latest URL

# Logs
docker compose logs -f techlens
tail -f /tmp/ngrok.log
```

### After Restart

```bash
# Stop services
docker compose down
pkill ngrok

# Start fresh (URL auto-updates)
./scripts/start_techlens_demo.sh

# Landing page reflects new URL automatically
```

---

## Troubleshooting

### ngrok URL not updating

**Check logs:**
```bash
cat /tmp/capture_ngrok.log
curl http://localhost:4040/api/tunnels
```

**Restart ngrok:**
```bash
pkill ngrok
sleep 2
nohup ngrok http 8000 > /tmp/ngrok.log 2>&1 &
./scripts/capture_ngrok_url.sh
```

### API endpoint returns "not found"

Verify the file exists:
```bash
ls -la /home/opc/techlens/current_ngrok_url.txt
cat /home/opc/techlens/current_ngrok_url.txt
```

### Landing page shows "Loading..." forever

Check browser console (F12) for CORS or network errors. Ensure:
```bash
docker compose ps  # Both services running
curl http://localhost:8000/api/current-url  # Endpoint works
```

### ngrok auth token issues

```bash
# Re-authenticate
ngrok config add-authtoken NEW_TOKEN

# Test
ngrok http 8000 --log=stdout
```

---

## Security Considerations

✅ **What's protected:**
- HTTPS (ngrok provides free SSL)
- Random URL makes it harder to guess
- Landing page doesn't expose app internals

⚠️ **Still add rate limiting:**

```python
# In src/techlens/api/main.py
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.get("/api/digest/daily")
@limiter.limit("30/minute")
def get_daily_digest(...):
    ...
```

---

## Cost Breakdown

| Item | Cost | Notes |
|---|---|---|
| ngrok free tier | $0 | 20 public URLs/month |
| GitHub Pages | $0 | Optional, for landing page |
| Oracle Cloud | $0 | Always Free tier |
| Total | **$0** | Completely free |

---

## Alternatives

### Without ngrok

- Oracle Load Balancer (free tier, setup more complex)
- Cloudflare free tier ($0, but requires domain)
- AWS API Gateway (free tier insufficient)

### With ngrok but simpler

- Manual URL sharing (send new URL each restart)
- Hardcoded URL in README (breaks on restart)
- Public IP (no HTTPS, less professional)

---

## Next Steps

1. Get ngrok auth token
2. Test locally first (on your Mac)
3. Deploy to Oracle Cloud
4. Create landing page
5. Share with hiring managers
6. Monitor and iterate

---

**Status:** Ready to implement ✅

**Questions before we start?**
