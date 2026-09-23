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

## Part 10: Troubleshooting

### Issue: Ollama stuck downloading model

```bash
# Check logs
docker logs ollama

# If stuck, restart Ollama
docker restart ollama

# Re-pull model
docker exec ollama ollama pull qwen3:14b
```

### Issue: Out of disk space

```bash
# Check disk usage
df -h

# Clean up Docker (removes unused images/containers)
docker system prune -a

# If still low, delete old Ollama models
docker exec ollama ollama rm <model-name>
```

### Issue: API not responding

```bash
# Check if containers are running
docker ps

# Check TechLens logs for errors
docker logs techlens

# Verify network connectivity
curl http://localhost:8000/health

# Check if port 8000 is listening
netstat -tuln | grep 8000
```

### Issue: Ollama API error (connection refused)

```bash
# Verify Ollama is running
docker ps | grep ollama

# Check if port 11434 is open
netstat -tuln | grep 11434

# Restart Ollama
docker restart ollama
```

---

## Part 11: Accessing from Your Mac

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

## Reference Commands

```bash
# SSH into instance
ssh -i ~/.ssh/your-private-key.key opc@<public-ip>

# View running containers
docker ps

# View all containers (including stopped)
docker ps -a

# Stop all containers
docker stop $(docker ps -q)

# View container logs
docker logs -f <container-name>

# Execute command in container
docker exec <container-name> <command>

# Delete container (stop first)
docker rm <container-name>

# Check Ollama models
docker exec ollama ollama list

# Test Ollama API
curl http://localhost:11434/api/tags

# Test TechLens API
curl http://localhost:8000/health
```

---

## Stack Summary

- **Compute:** Oracle Cloud VM.Standard.A1.Flex (2 OCPU, 12GB RAM, Always Free)
- **OS:** Oracle Linux 9
- **Runtime:** Docker
- **LLM:** Ollama + qwen3:14b
- **Backend:** Python 3.11 · FastAPI
- **Frontend:** React + TypeScript + Vite
- **Database:** SQLite
- **Vector DB:** ChromaDB
- **Package Manager:** uv

---

**Last updated:** 2026-09-23
**Status:** Production-ready for single-user local-first deployment

