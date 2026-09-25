# Automatic ngrok URL Management

When ngrok restarts, it gets a new public URL. This setup makes that automatic so the backend and frontend always use the current URL.

## How It Works

1. **`manage-ngrok.sh`** — Runs continuously, checks ngrok's API every 5 seconds
2. Detects when ngrok URL changes → updates `/home/opc/techlens/current_ngrok_url.txt`
3. Backend's `/api/config` endpoint serves the file → frontend always gets current URL
4. Systemd service auto-restarts if monitor crashes

## Setup on Oracle Cloud

### 1. Make script executable
```bash
chmod +x /home/opc/techlens/manage-ngrok.sh
```

### 2. Copy systemd service
```bash
sudo cp /home/opc/techlens/ngrok-monitor.service /etc/systemd/system/
```

### 3. Create log directory
```bash
sudo mkdir -p /var/log/techlens
sudo chown opc:opc /var/log/techlens
```

### 4. Enable and start service
```bash
sudo systemctl daemon-reload
sudo systemctl enable ngrok-monitor
sudo systemctl start ngrok-monitor
```

### 5. Verify it's running
```bash
sudo systemctl status ngrok-monitor
journalctl -u ngrok-monitor -f  # Watch live logs
```

## How It Solves the Problem

**Before:** ngrok URL hardcoded → must manually update when it changes  
**Now:** Script detects changes automatically → frontend & backend auto-discover via `/api/config`

## Demo Access

Users access the demo via GitHub Pages:
```
https://kirthistaank.github.io/join-demo.html?backend=https://current-ngrok-url.ngrok-free.dev
```

Or you can share the direct backend link (form auto-discovers it):
```
https://unwired-gear-glowing.ngrok-free.dev/
```

The form will:
1. Fetch `/api/config` to get current URL
2. Submit to `/api/join-demo` 
3. Get redirect token
4. Open the app

## Cleanup

If you need to stop the monitor:
```bash
sudo systemctl stop ngrok-monitor
sudo systemctl disable ngrok-monitor
sudo rm /etc/systemd/system/ngrok-monitor.service
sudo systemctl daemon-reload
```
