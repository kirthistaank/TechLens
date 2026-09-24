# Oracle Cloud Setup Guide for TechLens

Complete step-by-step guide to deploy TechLens on Oracle Cloud Always Free tier (VM.Standard.A1.Flex).

**Target audience:** Principal-level architect deploying local-first AI tech intelligence on ARM compute.

---

## Prerequisites

- Oracle Cloud Always Free account (cloud.oracle.com)
- Mac with SSH client installed (built-in)
- Downloaded private key from Oracle Cloud
- Instance: VM.Standard.A1.Flex with 2 OCPUs / 12 GB RAM

---

## Part 1: Oracle Cloud Instance Setup

### 1.1 Create Instance in Oracle Cloud Console

**Basic Information:**
- **Name:** `techlens-instance` (or your preference)
- **Compartment:** Root (or your default)
- **Availability Domain:** AD-1 (or any available)
- **Image:** Oracle Linux 9 (latest build)
- **Shape:** VM.Standard.A1.Flex
  - **OCPUs:** 2
  - **Memory:** 12 GB

**Networking:**
- **VCN:** Create new (`vcn-techlens`)
- **Subnet:** Create new (`subnet-techlens`)
- **CIDR Block:** `10.0.0.0/24`
- **Public IPv4 Address:** Select **Ephemeral public IP** (free, temporary but sufficient for dev)
- **SSH Key:** Upload your public key from Oracle Cloud

**Security (optional defaults are fine):**
- Secure Boot: Disabled
- Confidential Computing: Disabled
- Cloud Guard: Enabled (recommended)

**Storage:**
- Boot Volume: Default (50 GB standard)
- In-transit encryption: Enabled

Click **Create** and wait ~2 minutes for instance to boot.

---

### 1.2 Get SSH Access

**On your Mac, set up the SSH key:**

```bash
# Create .ssh directory if needed
mkdir -p ~/.ssh

# Move your private key (downloaded from Oracle Cloud)
cp ~/Downloads/your-private-key.key ~/.ssh/
chmod 600 ~/.ssh/your-private-key.key

# Verify permissions
ls -la ~/.ssh/your-private-key.key
# Should show: -rw------- (600)
```

**Get your instance's public IP:**
- Go to Oracle Cloud Console → **Compute > Instances**
- Click your instance
- Copy the **Public IPv4 Address** (e.g., `143.47.x.x`)

**SSH into the instance:**

```bash
ssh -i ~/.ssh/your-private-key.key opc@<public-ip>
```

Example:
```bash
ssh -i ~/.ssh/your-private-key.key opc@143.47.123.45
```

You should see the prompt:
```
[opc@techlens-instance ~]$
```

---

## Part 2: System Setup & Dependencies

Run these commands in your SSH session.

### 2.1 Update System & Install Prerequisites

```bash
# Update package manager
sudo dnf update -y

# Install essential tools
sudo dnf install -y \
  git \
  curl \
  wget \
  vim \
  net-tools

# Verify installed
git --version
```

### 2.2 Install Docker

```bash
# Install Docker Engine
sudo dnf install -y docker-engine

# Start Docker daemon
sudo systemctl start docker
sudo systemctl enable docker

# Add opc user to docker group (avoid sudo for docker commands)
sudo usermod -aG docker opc

# Apply group membership (requires new shell)
newgrp docker
```

**Reconnect SSH to apply group changes:**

```bash
exit
ssh -i ~/.ssh/your-private-key.key opc@<public-ip>
```

**Verify Docker is running:**

```bash
docker ps
# Should return: CONTAINER ID  IMAGE  COMMAND  CREATED  STATUS  PORTS  NAMES
# (no errors, maybe no containers yet)
```

---

## Part 3: Pull TechLens Code

### 3.1 Clone Repository

```bash
# Navigate to home directory
cd ~

# Clone TechLens repo
git clone https://github.com/yourusername/techlens.git
cd techlens

# Verify you have the project structure
ls -la
# Should show: src/, frontend/, tests/, docs/, README.md, etc.
```

If the repo is private, set up Git credentials:

```bash
# Configure Git with your credentials
git config --global user.email "your-email@example.com"
git config --global user.name "Your Name"

# Generate personal access token in GitHub (Settings > Developer settings > Personal access tokens)
# Then use it as password when prompted
```

### 3.2 Verify Project Structure

```bash
cd ~/techlens

# Check Python source
ls -la src/techlens/
# Should see: config.py, main.py, etc.

# Check if config.py exists
cat src/techlens/config.py | head -20
```

---

## Part 4: Ollama & TechLens Setup with Docker Compose

### 4.1 Start All Services

```bash
cd ~/techlens

# Start Ollama + TechLens backend using docker-compose
docker-compose up -d

# This will:
# 1. Pull Ollama image
# 2. Build TechLens backend
# 3. Pull qwen3:14b model (takes 5-10 min on first run)
# 4. Start both services

# Verify services are running
docker-compose ps
# Should show: ollama (healthy) and techlens (healthy)
```

### 4.2 Monitor Ollama Model Download

```bash
# Watch the Ollama service as it pulls qwen3:14b
docker-compose logs -f ollama

# When done, you'll see: "success"
# Press Ctrl+C to exit logs
```

**Verify Ollama is ready:**

```bash
# Check Ollama status
curl http://localhost:11434/api/tags
# Should return JSON with qwen3:14b listed

# Simple inference test
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3:14b",
  "prompt": "Hello, what is your name?",
  "stream": false
}'
# Should return a response from the model
```

### 4.3 Monitor TechLens Backend

```bash
# Watch TechLens startup logs
docker-compose logs -f techlens

# Should show:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

### 4.4 Useful Docker Compose Commands

```bash
# View all service logs
docker-compose logs

# Stop all services
docker-compose stop

# Start services (after stopping)
docker-compose start

# Restart services
docker-compose restart

# Remove containers (keeps volumes)
docker-compose down

# Remove everything including volumes
docker-compose down -v
```

---

## Part 4.5: Build Frontend (Required for Docker)

The Docker image includes the built frontend. You must build it first:

```bash
cd ~/techlens/frontend

# Install Node.js (one time only)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm install --lts

# Install npm dependencies
npm install

# Build production bundle
npm run build

# Verify dist folder was created
ls -la dist/
# Should show: index.html, css/, js/ folders

# Return to project root
cd ~/techlens
```

Without this step, Docker build will fail with: `"/frontend/dist": not found`

---

## Part 5: TechLens Configuration

### 5.1 Update config.py for Ollama URL

Edit the configuration file to point to your running Ollama service:

```bash
# Open config file in editor
nano ~/techlens/src/techlens/config.py
```

Find and update these lines:

```python
# Ollama settings
ollama_base_url: str = "http://localhost:11434"  # Points to Docker container
ollama_model: str = "qwen3:14b"  # Already set to qwen3:14b

# Database paths (absolute paths on instance)
database_url: str = "sqlite:////home/opc/techlens-data/techlens-db/techlens.db"

# ChromaDB path
chroma_path: str = "/home/opc/techlens-data/chroma"

# Ollama context window (CRITICAL - never omit)
ollama_num_ctx: int = 8192
```

**Save and exit (Ctrl+X, then Y, then Enter)**

### 5.2 Verify Config

```bash
# Check your changes were saved
grep -E "ollama_base_url|ollama_model|database_url|chroma_path" ~/techlens/src/techlens/config.py
```

---

## Part 6: Verify TechLens Backend

The backend is already running via docker-compose from Part 4. Here's how to verify:

### 6.1 Test the API

```bash
# Health check endpoint
curl http://localhost:8000/health

# Should return: {"status": "ok"}

# List available endpoints (open in browser on your Mac)
# http://<public-ip>:8000/docs
# (Interactive Swagger UI with all endpoints)
```

### 6.2 View Backend Logs

```bash
# View recent logs
docker-compose logs techlens

# Stream live logs
docker-compose logs -f techlens
```

### 6.3 Alternative: Run Directly (for development)

If you want to run without Docker (for debugging):

```bash
cd ~/techlens

# Install uv package manager (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Install dependencies
uv sync

# Start FastAPI backend (runs on port 8000)
# Make sure Ollama is running in another docker container
uv run uvicorn techlens.api.main:app --host 0.0.0.0 --port 8000

# Should show:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Application startup complete
```

---

## Part 7: Access Frontend

The frontend is already built and served by the backend!

### 7.1 Access the Web UI

The React frontend is automatically served from the TechLens backend as static files:

```bash
# Open in your Mac browser (from Part 11 SSH tunnel)
http://localhost:8000

# Or access directly from public IP
http://<public-ip>:8000
```

### 7.2 Frontend Build (If You Update Code)

If you modify the frontend code and need to rebuild:

```bash
cd ~/techlens/frontend

# Install Node.js (if not already installed)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="$HOME/.nvm"
source "$NVM_DIR/nvm.sh"
nvm install --lts

# Install dependencies (only first time)
npm install

# Build production bundle
npm run build

# Rebuild the TechLens Docker image to include new build
cd ~/techlens
docker-compose build --no-cache techlens

# Restart the backend
docker-compose restart techlens
```

### 7.3 Local Development (On Your Mac, Not Oracle)

If you want to develop locally with hot-reload:

```bash
# On your Mac (not SSH)
cd ~/techlens/frontend
npm run dev

# Frontend runs on http://localhost:5173
# Make sure backend is accessible (via SSH tunnel or public IP)
```

---

## Part 8: Verification & Testing

### 8.1 Check All Services

```bash
# Ollama container running
docker ps | grep ollama

# TechLens container running (if using Docker)
docker ps | grep techlens

# API responding
curl http://localhost:8000/health

# Ollama responding
curl http://localhost:11434/api/tags
```

### 8.2 Run Unit Tests

```bash
cd ~/techlens

# Run pytest with mocked providers
uv run pytest tests/unit/ -v

# Should pass: test_concept_extractor, test_synthesizer, test_trend_detector
```

### 8.3 Run Phase 1 Integration Test

```bash
cd ~/techlens

# End-to-end smoke test: RSS XML → digest
uv run pytest tests/integration/test_phase3_pipeline.py -v

# Should complete without errors
```

---

## Part 9: Persistent & Monitoring

### 9.1 View Logs

```bash
# Ollama logs
docker logs -f ollama

# TechLens logs (if Docker)
docker logs -f techlens

# Exit with Ctrl+C
```

### 9.2 Monitor Resources

```bash
# Check instance CPU/memory usage
top
# Press Q to exit

# Check disk usage
df -h

# Check Docker containers resource usage
docker stats
```

### 9.3 Persist Across Reboots

Containers are set to `--restart unless-stopped`, so they'll auto-restart if:
- Instance reboots
- Container crashes
- Docker daemon restarts

**To manually stop/start:**

```bash
# Stop containers
docker stop ollama techlens

# Start containers
docker start ollama techlens

# Restart containers
docker restart ollama techlens
```

---

## Part 10: Docker Build & Deployment

### 10.1 Docker Compose Setup

Docker Compose orchestrates both Ollama and TechLens backend with a single command:

```bash
cd ~/techlens

# Start all services
docker compose up -d

# Monitor the build (first time takes ~2-3 minutes)
docker compose logs -f techlens

# Check service status
docker compose ps
# Should show: ollama (healthy) and techlens (healthy)
```

### 10.2 Dockerfile Details

The Dockerfile (located at project root) does:
1. Starts with Python 3.11 base image
2. Installs `uv` package manager
3. Copies pyproject.toml and project source
4. Runs `uv sync` to install all dependencies
5. Creates persistent storage directories
6. Exposes port 8000
7. Starts Uvicorn server

Key environment variables set by docker-compose:
```yaml
OLLAMA_BASE_URL: http://ollama:11434
OLLAMA_MODEL: qwen3:14b
OLLAMA_NUM_CTX: 8192
DATABASE_URL: sqlite:////data/db/techlens.db
CHROMA_PATH: /data/chroma
```

### 10.3 Useful Docker Compose Commands

```bash
# View all services
docker compose ps

# View logs
docker compose logs techlens
docker compose logs ollama
docker compose logs -f  # Stream live

# Restart services
docker compose restart techlens
docker compose restart ollama

# Stop all
docker compose stop

# Start all
docker compose start

# Remove containers (keeps data)
docker compose down

# Remove everything including volumes
docker compose down -v

# Rebuild image (after code changes)
docker compose build --no-cache techlens
```

---

## Part 11: Troubleshooting Docker & Deployment

### Issue: `docker-compose: command not found`

**Solution:** Use `docker compose` (with space, not hyphen). Modern Docker includes Compose as a subcommand:

```bash
docker compose up -d  # Correct
docker-compose up -d  # Wrong (old syntax)
```

### Issue: Docker build fails with `/frontend/dist: not found`

**Error:**
```
failed to compute cache key: ... "/frontend/dist": not found
```

**Solution:** Build the frontend first:

```bash
cd ~/techlens/frontend
npm install
npm run build
cd ~/techlens
docker compose build --no-cache techlens
```

### Issue: Docker build fails with `uv sync` error

**Error:**
```
error: Unable to find lockfile at `uv.lock`, but `--frozen` was provided
```

**Solution:** Use the updated Dockerfile (just `RUN uv sync`, not `--frozen`).

### Issue: Ollama stuck downloading model

```bash
docker compose logs ollama
docker compose restart ollama
docker exec techlens-ollama ollama pull qwen3:14b
```

### Issue: Out of disk space

```bash
df -h
docker system prune -a
docker exec techlens-ollama ollama rm <model-name>
```

### Issue: API not responding

```bash
docker compose ps
docker compose logs techlens
curl http://localhost:8000/health
netstat -tuln | grep 8000
```

### Issue: TechLens backend crashes

```bash
docker compose logs techlens  # Check full logs
docker compose restart techlens
docker compose logs -f techlens  # Stream logs
```

### Issue: Database permission denied

```bash
docker compose exec techlens bash
chmod 777 /data/db
docker compose restart techlens
```

### Issue: Frontend blank page

```bash
ls -la ~/techlens/frontend/dist/
docker compose exec techlens ls -la /app/frontend/dist/
cd ~/techlens/frontend && npm run build
cd ~/techlens && docker compose build --no-cache techlens
docker compose restart techlens
```

### Issue: SSH connection timeout (`Operation timed out`)

**Error:**
```
ssh: connect to host 129.146.58.128 port 22: Operation timed out
```

**Root cause:** Instance is not reachable (stopped, no public IP, or network issue).

**Solution — Step 1: Check instance status**

Go to Oracle Cloud Console:
1. **Compute > Instances**
2. Click your instance
3. Verify **Instance State** = "Running"
4. Copy current **Public IPv4 Address** (may have changed if Ephemeral)

**Solution — Step 2: Try SSH with verbose output**

```bash
# See what's happening
ssh -v -i ~/.ssh/your-private-key.key opc@<public-ip>

# Look for:
# - "Connecting to..."
# - "Connected"
# - Any error messages
```

**Solution — Step 3: If instance is stopped, restart it**

```bash
# In Oracle Cloud Console:
# Click instance → More Actions → Start

# Then try SSH again (wait 30 seconds for boot)
ssh -i ~/.ssh/your-private-key.key opc@<public-ip>
```

**Solution — Step 4: If IP changed (Ephemeral)**

Ephemeral IPs change when instance stops/starts:

```bash
# Get new IP from Oracle Console
# Then SSH to the new IP
ssh -i ~/.ssh/your-private-key.key opc@<new-public-ip>
```

To keep the same IP, use a **Reserved Public IP** (costs money, not recommended for portfolio).

### Issue: SSH tunnel connection slow or hanging

**Error:**
```
ssh -L 8000:localhost:8000 opc@129.146.58.128
# Hangs or takes 30+ seconds
```

**Solution:**

```bash
# Add verbose output to see what's happening
ssh -v -L 8000:localhost:8000 opc@<public-ip>

# With timeout (30 seconds)
timeout 30 ssh -L 8000:localhost:8000 opc@<public-ip>

# Once connected, test the tunnel
curl http://localhost:8000/api/digest/daily
```

SSH tunnels can be slow on high-latency connections. If it eventually connects (after 30-60 seconds), it's working fine.

### Issue: SSH tunnel syntax error

**Error:**
```
Bad local forwarding specification '8000'
```

**Solution:** Remove space in `-L` flag:

```bash
# ❌ Wrong (space after 8000)
ssh -L 8000 :localhost:8000 opc@<public-ip>

# ✅ Correct (no space)
ssh -L 8000:localhost:8000 opc@<public-ip>
```

### Issue: HTTP 404 on `/health` endpoint

**Error:**
```
curl http://localhost:8000/health
{"detail":"Not Found"}
```

**Solution:** `/health` endpoint doesn't exist. Use valid endpoints:

```bash
# Get daily digest
curl http://localhost:8000/api/digest/daily

# View API docs
curl http://localhost:8000/docs

# Or add a /health endpoint to routes.py (optional)
```

### Issue: Ollama container unhealthy (health check fails)

**Error:**
```
Container techlens-ollama Error dependency ollama failed to start
container techlens-ollama is unhealthy
```

**Root cause:** Health check is too strict, or Ollama API takes time to respond.

**Solution — Change health check dependency:**

Edit `docker-compose.yml`:

```yaml
techlens:
  depends_on:
    ollama:
      condition: service_started  # Changed from service_healthy
```

Then:
```bash
docker compose up -d
docker compose ps  # Both should be running
```

**Or disable health check on Ollama entirely:**

In `docker-compose.yml`, remove or comment out the `healthcheck:` block under `ollama:`.

### Issue: Public IP not accessible (403 / Connection refused)

**Error:**
```
curl http://129.146.58.128:8000
curl: (7) Failed to connect to 129.146.58.128 port 8000: Connection refused
```

**Root cause:** Security Group doesn't allow inbound traffic on port 8000.

**Solution:**

1. Go to Oracle Cloud Console → **Compute > Instances**
2. Click instance → **Primary VNIC**
3. Click security group name
4. **Ingress Rules** → **Add Ingress Rule**:
   - Stateless: No
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: TCP
   - Source Port Range: (leave blank)
   - Destination Port Range: `8000`
   - Click **Add**

5. Wait 30 seconds, then test:
```bash
curl http://129.146.58.128:8000/api/digest/daily
```

**For SSH access (port 22), ensure it's also open:**
- Port: `22`
- Source CIDR: Your IP (e.g., `203.0.113.0/24`) — restrict for security

### Issue: "No space left on device" when pulling models

**Error:**
```
Error: write /root/.ollama/models/blobs/...: no space left on device
```

**Root cause:** Partial failed downloads consume space, or root filesystem is full.

**Solution — Step 1: Check available space**

```bash
# See what's using space
df -h
# Look for 100% usage on /dev/mapper/ocivolume-root

# Find large files/directories
du -sh /* | sort -rh | head -10

# Detailed breakdown
du -sh /home /var /usr /opt
```

**Solution — Step 2: Delete partial Docker blobs**

```bash
# Stop Ollama to release file locks
docker compose stop ollama

# Delete incomplete/partial downloads
sudo rm -rf /var/lib/docker/volumes/techlens_ollama-models/_data/blobs/*-partial

# Delete any orphaned model directories
sudo rm -rf /home/opc/techlens/models/

# Clean Docker system
docker system prune -a --volumes -f
docker volume prune -f
```

**Solution — Step 3: Clean package manager cache**

```bash
# Clean DNF (package manager) cache
sudo dnf clean all
sudo dnf autoremove -y

# Clean package database
sudo rm -rf /var/cache/dnf/*
```

**Solution — Step 4: Clean unnecessary project files**

```bash
cd ~/techlens

# Remove node_modules (usually 300-500MB)
rm -rf frontend/node_modules

# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name .pytest_cache -exec rm -rf {} +
rm -rf .venv .pytest_cache
```

**Solution — Step 5: Clean system logs**

```bash
# Clean old journal logs (keep last 100MB)
sudo journalctl --vacuum=100M

# Clean old log files
sudo rm -rf /var/log/*.gz /var/log/*.1
sudo rm -rf /var/log/audit/*
```

**Solution — Step 6: Remove Docker volume completely and recreate**

```bash
# Remove the volume that has partial data
docker volume rm techlens_ollama-models

# Verify it's gone
docker volume ls | grep ollama-models

# Space should be freed now
df -h
```

**Solution — Step 7: Retry model pull**

```bash
# Start Ollama fresh
docker compose up -d ollama
sleep 30

# Pull smaller model (mistral:7b is ~4.7GB, not 9GB)
docker compose exec ollama ollama pull mistral:7b

# Watch progress
docker compose logs -f ollama
```

**Prevention — Use smaller models**

| Model | Size | Use Case |
|---|---|---|
| mistral:7b | 4.7 GB | ✅ Recommended for portfolio |
| llama2:7b | 4 GB | Good alternative |
| qwen3:7b | ~4 GB | If available |
| ❌ qwen3:14b | 9 GB | Too large for 30GB root |

**Prevention — Keep space headroom**

```bash
# Before pulling model, ensure 10GB+ free
df -h
# If less than 10GB free, do cleanup first

# Monitor space regularly
watch -n 5 'df -h | grep ocivolume'
```

**Prevention — Use Always Free tier efficiently**

- **Don't** add extra block volumes (costs money)
- **Keep** only essential Docker images
- **Delete** node_modules after frontend build (rebuild when needed)
- **Use** smaller models (7B instead of 14B)
- **Prune** Docker regularly: `docker system prune -a --volumes -f`

**Quick cleanup script** (run anytime):

```bash
#!/bin/bash
# Save as ~/cleanup.sh

echo "Cleaning TechLens storage..."

# Stop services
docker compose stop ollama techlens

# Remove partial blobs
sudo rm -rf /var/lib/docker/volumes/techlens_ollama-models/_data/blobs/*-partial
sudo rm -rf /home/opc/techlens/models/

# Clean Docker
docker system prune -a --volumes -f
docker builder prune -a -f

# Clean system
sudo dnf clean all
sudo journalctl --vacuum=100M

# Report
echo "Cleanup complete!"
df -h | grep ocivolume-root
```

Run it:
```bash
bash ~/cleanup.sh
```

---

## Part 11: Accessing Frontend from Your Mac

### 11.1 Direct Access (via Public IP)

If Security Groups allow public access:

```bash
# Open in your Mac browser:
http://<public-ip>:8000

# Example:
http://129.146.58.128:8000
```

**To enable public access:**
1. Go to Oracle Cloud Console → **Compute > Instances**
2. Click your instance
3. **Primary VNIC** → Security group
4. **Ingress Rules** → Add:
   - Source CIDR: `0.0.0.0/0`
   - Protocol: TCP
   - Port: 8000

### 11.2 SSH Tunnel (Recommended for Security)

**On your Mac, create a tunnel** (keep this terminal open):

```bash
ssh -i ~/.ssh/your-private-key.key -L 8000:localhost:8000 opc@<public-ip>
```

Example:
```bash
ssh -i ~/.ssh/ssh-key-2026-09-23-oracle-techlens.key -L 8000:localhost:8000 opc@129.146.58.128
```

**Then in your browser:**
```
http://localhost:8000
```

This tunnels port 8000 through SSH (encrypted, secure).

### 11.3 Access API Documentation

```
http://<public-ip>:8000/docs
# or via tunnel:
http://localhost:8000/docs
```

Interactive Swagger UI with all endpoints.

---

## Part 12: Accessing from Your Mac

### Option A: SSH Tunnel (Recommended)

Create a tunnel to access the instance APIs from your Mac:

```bash
# On your Mac, open a new Terminal tab
ssh -i ~/.ssh/your-private-key.key -L 8000:localhost:8000 opc@<public-ip>

# Now on your Mac, open browser:
# http://localhost:8000/docs (TechLens API)

# Keep this terminal open for the tunnel to work
```

### Option B: Direct Access via Public IP

If you exposed the API to the public (not recommended for security):

```bash
# In your Mac browser:
http://<public-ip>:8000/docs
```

---

## Part 12: Next Steps

### Scale the Deployment

- **Add more models:** `docker exec ollama ollama pull <model-name>`
- **Increase storage:** Add block volumes in Oracle Cloud Console
- **Set up monitoring:** Use Oracle Cloud Monitoring or Prometheus
- **Automate ingestion:** Configure APScheduler jobs in config.py

### Optimize Performance

- Monitor RAM usage: `docker stats`
- If hitting 12GB limit, consider splitting Ollama and TechLens onto separate instances
- Use `keep_alive` setting in config to unload models between calls (saves RAM, trades for slower inference)

### Secure the Deployment

- Restrict SSH access via Security Groups (Oracle Cloud Console)
- Use Bastion host for production (VCN isolation)
- Enable VPN access via Tailscale (https://tailscale.com) for private access

---

## Part 13: Common Issues Summary

| Issue | Solution |
|---|---|
| SSH timeout | Check instance is running, restart if needed |
| SSH tunnel slow | Normal, can take 30-60s on high-latency links |
| Public IP not accessible | Add port 8000 to Security Group ingress rules |
| `/health` endpoint 404 | Use `/api/digest/daily` or add `/health` endpoint |
| Ollama container unhealthy | Change `depends_on` condition to `service_started` |
| No space left on device | Run cleanup script: `docker system prune -a --volumes -f` |
| Docker build fails | Check frontend/dist exists, run `npm run build` first |

---

## Part 14: Docker Compose vs Manual Docker

### Why docker-compose.yml?

Instead of running multiple manual `docker run` commands:

```bash
# ❌ Manual (error-prone, hard to manage)
docker run -d --name ollama ollama/ollama:latest
docker run -d --name techlens --link ollama:ollama techlens:latest
# ...many more flags
```

Use docker-compose (single source of truth):

```bash
# ✅ Docker Compose (clean, reproducible)
docker compose up -d
docker compose down
docker compose restart
```

### Files Created for TechLens

| File | Purpose |
|---|---|
| `Dockerfile` | Build TechLens backend image |
| `docker-compose.yml` | Orchestrate Ollama + TechLens |
| `.dockerignore` | Exclude unnecessary files from build |

---

## Part 15: Deployment Checklist

Before going to production, verify:

- [ ] Instance is running and has public IP
- [ ] SSH access works: `ssh -i ~/.ssh/key opc@<public-ip>`
- [ ] Docker Compose is running: `docker compose ps` (both containers up)
- [ ] Ollama model is pulled: `docker compose exec ollama ollama list`
- [ ] Backend responds: `curl http://localhost:8000/api/digest/daily`
- [ ] Frontend accessible: `http://<public-ip>:8000` or SSH tunnel
- [ ] Security Groups allow port 8000 (if public) and 22 (SSH)
- [ ] Disk space is adequate: `df -h` (at least 10GB free)
- [ ] Model is appropriate size (mistral:7b ~4.7GB, not qwen3:14b ~9GB)

---

## Part 16: Reference Commands

### Docker Compose Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose stop

# Restart specific service
docker compose restart techlens
docker compose restart ollama

# View logs
docker compose logs
docker compose logs -f techlens  # Stream TechLens logs
docker compose logs -f ollama    # Stream Ollama logs

# Execute command in container
docker compose exec techlens bash
docker compose exec ollama ollama list

# Remove containers (keeps data)
docker compose down

# Remove everything including volumes
docker compose down -v

# Rebuild image after code changes
docker compose build --no-cache techlens
```

### SSH & System Commands

```bash
# SSH into instance
ssh -i ~/.ssh/your-private-key.key opc@<public-ip>

# Check disk usage
df -h

# Check instance CPU/memory
top

# View network connections
netstat -tuln

# View running processes
ps aux | grep docker
ps aux | grep ollama
```

### Manual Docker Commands (if not using compose)

```bash
# View running containers
docker ps

# View all containers
docker ps -a

# View container logs
docker logs -f <container-name>

# Stop specific container
docker stop <container-id>

# Delete container
docker rm <container-id>

# Check Docker disk usage
docker system df
```

### API Testing

```bash
# Test Ollama health
curl http://localhost:11434/api/tags

# Test TechLens health
curl http://localhost:8000/health

# List all Ollama models
docker compose exec ollama ollama list

# Test inference
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3:14b",
  "prompt": "What is TechLens?",
  "stream": false
}'
```

---

## Part 15: What Was Changed During Setup

### Docker Files Created
- **Dockerfile:** Multi-stage Python build, installs deps with uv, serves frontend + backend
- **docker-compose.yml:** Orchestrates Ollama + TechLens with health checks
- **.dockerignore:** Excludes unnecessary files from Docker context

### Fixes Applied to Files
| Issue | Fix | File |
|---|---|---|
| `/frontend/dist/` missing | Build frontend before Docker build | oracle-cloud-setup.md |
| `uv venv` + pip not found | Simplified to `uv sync` | Dockerfile |
| Obsolete version field | Removed `version: '3.8'` | docker-compose.yml |
| `--frozen` lock file error | Removed `--frozen` flag | Dockerfile |

### Common Gotchas Discovered
1. **Frontend build required** — Must run `npm run build` before Docker build
2. **uv.lock not present** — Can't use `--frozen` without lock file
3. **docker-compose vs docker compose** — New Docker uses space, not hyphen
4. **Ollama model download** — Takes 5-10 min on first run, be patient

---

## Stack Summary

- **Compute:** Oracle Cloud VM.Standard.A1.Flex (2 OCPU, 12GB RAM, Always Free)
- **OS:** Oracle Linux 9
- **Container Runtime:** Docker with Docker Compose
- **Orchestration:** docker-compose.yml (Ollama + TechLens)
- **LLM:** Ollama + qwen3:14b (~9GB)
- **Backend:** Python 3.11 · FastAPI · Uvicorn
- **Frontend:** React + TypeScript + Vite (built → served as static files)
- **Database:** SQLite (persisted to `/data/db/`)
- **Vector DB:** ChromaDB (persisted to `/data/chroma/`)
- **Package Manager:** uv (fast Python package management)

---

## Quick Start (After Instance Setup)

```bash
# 1. SSH into instance
ssh -i ~/.ssh/key opc@<public-ip>

# 2. Clone repo
cd ~ && git clone <repo-url> && cd techlens

# 3. Build frontend
cd frontend && npm install && npm run build && cd ..

# 4. Start all services
docker compose up -d

# 5. Verify
docker compose ps
curl http://localhost:8000/health
```

---

**Last updated:** 2026-09-23  
**Status:** Production-ready for single-user local-first AI tech intelligence  
**Verified on:** Oracle Cloud VM.Standard.A1.Flex · Oracle Linux 9 · Docker Compose v5.5.1

