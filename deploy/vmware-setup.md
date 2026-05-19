# VMware + Cloudflare Tunnel Setup Guide
# Turn Your Development PC into a Cloud-Connected Server

## Architecture

```
Streamlit Cloud (Dashboard)
         │
         ▼
Cloudflare Tunnel (HTTPS, free, persistent URL)
         │
         ▼
Your PC (Windows) → VMware Ubuntu VM → Docker (Ollama + n8n)
```

**Why Cloudflare Tunnel?**
- Free forever
- No port forwarding on your router
- Your home IP stays private
- Automatic HTTPS
- Persistent URL even if your IP changes

---

## Step 1: Install VMware Workstation Player (Free)

1. Go to [support.broadcom.com](https://support.broadcom.com/security-advisory/security-advisory-detail.html?securit-advisory-id=SA24541)
   - Or search "VMware Workstation Player 17 download"
2. Download **VMware Workstation 17 Player** (free for personal use)
3. Run the installer → Follow prompts → Restart PC if asked

---

## Step 2: Create Ubuntu VM

1. Download **Ubuntu 22.04 LTS Server ISO**:
   - Go to [ubuntu.com/download/server](https://ubuntu.com/download/server)
   - Download the 64-bit ISO (~2 GB)

2. Open VMware Workstation Player → **"Create a New Virtual Machine"**

3. **Installer disc image file**: Browse to your Ubuntu ISO

4. **Easy Install Information**:
   - Full name: `Olympic HR`
   - Username: `olympic`
   - Password: `olympic123` (write this down!)

5. **Virtual Machine Name**: `olympic-hr-server`
   - Location: Pick a folder with at least 50 GB free space

6. **Disk Capacity**:
   - Maximum disk size: `50.0 GB`
   - Select **"Split virtual disk into multiple files"**

7. **Customize Hardware** (click button before finishing):
   - **Memory**: 8192 MB (8 GB) minimum, 12288 MB (12 GB) recommended
   - **Processors**: 2 cores minimum, 4 cores recommended
   - **Network Adapter**: NAT (default)
   - Close → **Finish**

8. **Power on** the VM. Ubuntu will install automatically (Easy Install).
   - Wait ~15-20 minutes.

9. When you see the login prompt, the VM is ready.

---

## Step 3: First Login & Update

### Log into the VM
In the VMware console, log in with:
- Username: `olympic`
- Password: `olympic123`

### Get the VM's IP address
```bash
ip addr show
```
Look for `inet 192.168.x.x` under `ens160` — this is your VM's internal IP. Write it down.

### Update Ubuntu
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git
```

---

## Step 4: Install Docker & Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add user to docker group (so you don't need sudo)
sudo usermod -aG docker $USER

# Apply group change
newgrp docker

# Verify
docker --version
docker compose version
```

---

## Step 5: Clone Repo & Start Ollama + n8n

```bash
cd ~
git clone https://github.com/Riad154/Olympic-Resume-Ranking-.git
cd Olympic-Resume-Ranking-/deploy

# Start services
docker compose up -d

# Pull the AI model (takes 5-15 min)
docker compose exec ollama ollama pull qwen3:8b-q4_K_M

# Verify
docker ps
curl http://localhost:11434/api/tags
curl http://localhost:5678/healthz
```

---

## Step 6: Install Cloudflare Tunnel (cloudflared)

This creates a secure tunnel from your VM to the public internet.

### Step 6.1: Install cloudflared
```bash
# Download and install
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Verify
cloudflared --version
```

### Step 6.2: Authenticate with Cloudflare
```bash
cloudflared tunnel login
```
- This prints a URL. Open it in your browser.
- Log in to Cloudflare (create free account if needed).
- Select your domain (or use a free `*.trycloudflare.com` subdomain).
- Authorize → Download the certificate.
- The tunnel is now authenticated.

### Step 6.3: Create the Tunnel
```bash
# Create a named tunnel
cloudflared tunnel create olympic-hr

# This outputs a tunnel ID like: 1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p
# Copy the tunnel ID — you'll need it

# Create config file
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: YOUR_TUNNEL_ID_HERE
credentials-file: /home/olympic/.cloudflared/YOUR_TUNNEL_ID_HERE.json

ingress:
  - hostname: ollama.yourdomain.com
    service: http://localhost:11434
  - hostname: n8n.yourdomain.com
    service: http://localhost:5678
  - service: http_status:404
EOF
```

**Replace in the file above:**
- `YOUR_TUNNEL_ID_HERE` → your actual tunnel ID
- `yourdomain.com` → your actual domain (or use `trycloudflare.com` for a random subdomain)

### Step 6.4: Route DNS (if you have your own domain)
If using your own domain:
```bash
cloudflared tunnel route dns YOUR_TUNNEL_ID_HERE ollama.yourdomain.com
cloudflared tunnel route dns YOUR_TUNNEL_ID_HERE n8n.yourdomain.com
```

If using trycloudflare (random subdomain), skip this step.

### Step 6.5: Run the Tunnel
```bash
# Start tunnel (foreground, for testing)
cloudflared tunnel run olympic-hr
```

You should see output like:
```
2025-XX-XXTXX:XX:XXZ INF Connection registered connIndex=0
2025-XX-XXTXX:XX:XXZ INF Updated to new configuration config=null
```

**Keep this running for now.** Open a new terminal in the VM (right-click tab → New Tab) for the next steps.

---

## Step 7: Get Your Public URLs

If using **trycloudflare** (free random subdomain):
The tunnel URL will be printed in the terminal, like:
```
https://random-words.trycloudflare.com
```

Your service URLs become:
- Ollama: `https://random-words.trycloudflare.com/ollama`
- n8n: `https://random-words.trycloudflare.com/n8n`

If using **your own domain**:
- Ollama: `https://ollama.yourdomain.com`
- n8n: `https://n8n.yourdomain.com`

**Write these URLs down.**

---

## Step 8: Make Tunnel Run Forever (Systemd Service)

In your new terminal tab:

```bash
# Install as a systemd service
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared

# Check status
sudo systemctl status cloudflared
```

Now the tunnel auto-starts when the VM boots.

---

## Step 9: Configure Streamlit Cloud Secrets

Go to Streamlit Cloud dashboard → **Manage app → Secrets**:

```toml
# ── PostgreSQL (Neon) ─────────────────────────────────────────────────────
[postgresql]
host = "your-project.neon.tech"
port = "5432"
dbname = "neondb"
user = "neondb_owner"
password = "your-neon-password"

# ── Remote Ollama (Cloudflare Tunnel URL) ──────────────────────────────────
OLLAMA_HOST = "https://random-words.trycloudflare.com"
OLLAMA_MODEL = "qwen3:8b-q4_K_M"

# ── Remote n8n (Cloudflare Tunnel URL) ─────────────────────────────────────
N8N_HOST = "https://random-words.trycloudflare.com"

# ── GitHub Actions trigger ─────────────────────────────────────────────────
[github]
token = "ghp_xxxxxxxxxxxxxxxxxxxx"
repo = "Riad154/Olympic-Resume-Ranking-"

# ── BDJobs credentials ─────────────────────────────────────────────────────
[bdjobs]
username = "your_bdjobs_username"
password = "your_bdjobs_password"
```

**Important:** If using trycloudflare, the URL changes every time you restart the tunnel. For production, use your own domain (free on Cloudflare) or consider the static subdomain option.

For a **permanent free subdomain**, you can:
1. Buy a cheap domain (~$3-5/year on Namecheap) or use a free subdomain
2. Point it to Cloudflare's nameservers
3. Use the permanent domain in your tunnel config

---

## Step 10: Verify in Streamlit Cloud

Open your app → **Settings** page. You should see:
- **🟢 PostgreSQL** — Connected
- **🟢 Ollama** — 1 model(s) loaded
- **🟢 n8n** — Running

---

## Keeping Your PC Running

Since this is a local server:

1. **Disable Windows sleep**: Control Panel → Power Options → Set "Sleep" to "Never"
2. **Disable VM suspension**: In VMware → VM Settings → Options → Power → Uncheck "Suspend"
3. **Auto-start VM** (optional): VMware → Edit → Preferences → "Start up" → Select your VM

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Tunnel URL changes on restart | Use your own domain, or buy a cheap one ($3/year) |
| Ollama slow on CPU | Your PC needs a decent CPU. 4+ cores recommended. |
| VM won't start | Check VMware logs. Ensure virtualization is enabled in BIOS (Intel VT-x / AMD-V). |
| "Not reachable" in Settings | Check `docker ps` and `sudo systemctl status cloudflared` |
| High latency from Streamlit Cloud | Expected — data travels Streamlit Cloud → Cloudflare → Your PC. Still usable for ranking. |

---

## Cost Summary

| Component | Cost |
|---|---|
| VMware Workstation Player | **Free** (personal use) |
| Ubuntu | **Free** |
| Docker + Ollama + n8n | **Free** (open source) |
| Cloudflare Tunnel | **Free** forever |
| PostgreSQL (Neon) | **Free** (500 MB) |
| Streamlit Cloud | **Free** |
| **Total** | **$0** |
