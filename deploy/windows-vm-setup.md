# Windows 10 VM Setup Guide
# Run Ollama + n8n inside your Windows 10 Virtual Machine

## Architecture

```
Your Host PC (Windows/Linux/Mac)
         │
         ▼ (VM software: VMware/VirtualBox/Hyper-V)
    Windows 10 VM
         │
         ├── Ollama (native Windows)
         ├── n8n (Docker Desktop)
         └── Cloudflare Tunnel
                  │
                  ▼
         Public HTTPS URL
                  │
                  ▼
         Streamlit Cloud (Dashboard)
```

## Prerequisites for the VM

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB | 12-16 GB |
| CPU cores | 2 | 4 |
| Disk space | 30 GB | 50 GB |
| Network | Bridged or NAT | Bridged (gets own IP) |

---

## Step 1: Configure VM Network (IMPORTANT)

Before installing anything, set the VM network mode:

### If using VMware:
1. VM → Settings → Network Adapter
2. Select **"Bridged"** (VM gets its own IP on your network)
3. OR use **"NAT"** (simpler, but needs port forwarding for direct access)

### If using VirtualBox:
1. Settings → Network → Adapter 1
2. Attached to: **"Bridged Adapter"**
3. Name: Select your physical network card

### If using Hyper-V:
1. Virtual Switch Manager → Create "External" switch
2. Connect VM to that switch

**Why this matters**: Cloudflare Tunnel works through NAT or Bridged. Bridged is simpler for troubleshooting.

---

## Step 2: Install Ollama on Windows 10 VM

Inside your Windows 10 VM:

1. Open browser → go to **ollama.com**
2. Click **"Download for Windows"**
3. Run installer → accept all defaults
4. Ollama starts automatically (runs in system tray)

### Verify installation:
```cmd
# Open Command Prompt or PowerShell
ollama --version
```

### Pull the AI model:
```cmd
ollama pull qwen3:8b-q4_K_M
```
Wait 5-15 minutes (5 GB download).

### Test:
```cmd
curl http://localhost:11434/api/tags
```
Should show JSON with your model listed.

---

## Step 3: Install Docker Desktop

Inside the Windows 10 VM:

1. Go to **docker.com**
2. Download **Docker Desktop for Windows**
3. Run installer
4. When prompted:
   - ✓ Use WSL 2
   - ✓ Add to PATH
5. **Restart** the VM if prompted
6. Open Docker Desktop, skip sign-in (or create free account)
7. Wait for "Docker Desktop is running" status

### Verify:
```cmd
docker --version
docker compose version
```

---

## Step 4: Start n8n

Inside the Windows 10 VM:

1. Create folder for n8n data:
```cmd
mkdir C:\n8n-data
```

2. Run n8n container:
```cmd
docker run -d --name n8n -p 5678:5678 -v C:\n8n-data:/home/node/.n8n -e N8N_BASIC_AUTH_ACTIVE=true -e N8N_BASIC_AUTH_USER=admin -e N8N_BASIC_AUTH_PASSWORD=changeme123 n8nio/n8n
```

3. Verify:
```cmd
curl http://localhost:5678/healthz
```
Should return `{"status":"ok"}`

---

## Step 5: Install Cloudflare Tunnel

This exposes your VM's Ollama + n8n to the internet.

### 5.1 Download cloudflared
Inside the Windows 10 VM:

1. Go to: `github.com/cloudflare/cloudflared/releases/latest`
2. Download: `cloudflared-windows-amd64.exe`
3. Rename to `cloudflared.exe`
4. Move to `C:\Windows\System32\` (or any folder in PATH)

### 5.2 Create config folder
```cmd
mkdir C:\cloudflare-tunnel
cd C:\cloudflare-tunnel
```

### 5.3 Authenticate
```cmd
cloudflared.exe tunnel login
```
- Opens browser → Sign in to Cloudflare (free account)
- Click **Authorize**
- Certificate downloads automatically

### 5.4 Create tunnel
```cmd
cloudflared.exe tunnel create olympic-hr
```
**Copy the tunnel ID** shown (looks like: `1a2b3c4d-...`)

### 5.5 Create config file
Create file `C:\cloudflare-tunnel\config.yml`:

```yaml
tunnel: YOUR_TUNNEL_ID_HERE
credentials-file: C:\Users\YOUR_VM_USERNAME\.cloudflared\YOUR_TUNNEL_ID_HERE.json

ingress:
  - hostname: ollama.yourdomain.com
    service: http://localhost:11434
    originRequest:
      noTLSVerify: true
  - hostname: n8n.yourdomain.com
    service: http://localhost:5678
    originRequest:
      noTLSVerify: true
  - service: http_status:404
```

Replace:
- `YOUR_TUNNEL_ID_HERE` → your actual tunnel ID
- `YOUR_VM_USERNAME` → your Windows 10 VM username
- `yourdomain.com` → your domain (see options below)

### 5.6 DNS Options

**Option A: Use your own domain (permanent URL)**
- Have a domain (any domain)
- Point it to Cloudflare
- Create DNS records:
```cmd
cloudflared.exe tunnel route dns YOUR_TUNNEL_ID ollama.yourdomain.com
cloudflared.exe tunnel route dns YOUR_TUNNEL_ID n8n.yourdomain.com
```

**Option B: Free trycloudflare subdomain (URL changes on restart)**
- Skip DNS step
- Tunnel gives random URL like `https://abc123.trycloudflare.com`

### 5.7 Start tunnel
```cmd
cd C:\cloudflare-tunnel
cloudflared.exe tunnel --config config.yml run olympic-hr
```

**Keep this window open.** The tunnel is now running.

**Your public URL:**
- If using your domain: `https://ollama.yourdomain.com`
- If using trycloudflare: `https://random-words.trycloudflare.com` (shown in terminal)

**Write this URL down.**

---

## Step 6: Configure Streamlit Cloud

Go to Streamlit Cloud dashboard → Manage app → Secrets:

```toml
[postgresql]
host = "your-project.neon.tech"
port = "5432"
dbname = "neondb"
user = "neondb_owner"
password = "your-neon-password"

OLLAMA_HOST = "https://ollama.yourdomain.com"
OLLAMA_MODEL = "qwen3:8b-q4_K_M"

N8N_HOST = "https://n8n.yourdomain.com"

[github]
token = "ghp_xxxxxxxxxxxxxxxxxxxx"
repo = "Riad154/Olympic-Resume-Ranking-"

[bdjobs]
username = "your_bdjobs_username"
password = "your_bdjobs_password"
```

Save → App restarts.

---

## Step 7: Verify

Open your Streamlit Cloud app → Settings page.

You should see:
- 🟢 PostgreSQL — Connected
- 🟢 Ollama — 1 model(s) loaded  
- 🟢 n8n — Running

---

## Step 8: Make Tunnel Auto-Start

The tunnel stops when you close the command window. Let's fix that.

### Option A: Windows Service (NSSM)

1. Download NSSM from nssm.cc
2. Extract `nssm.exe` to `C:\Windows\System32\`
3. Install service:
```cmd
nssm install CloudflareTunnel
```
4. In the GUI:
   - Path: `C:\Windows\System32\cloudflared.exe`
   - Startup directory: `C:\cloudflare-tunnel`
   - Arguments: `tunnel --config C:\cloudflare-tunnel\config.yml run olympic-hr`
5. Click Install service
6. Start it:
```cmd
nssm start CloudflareTunnel
```

### Option B: Task Scheduler

1. Open Task Scheduler
2. Create Task → Name: `Cloudflare Tunnel`
3. General: Check "Run whether user is logged on or not"
4. Triggers: New → At startup
5. Actions: New → Start a program
   - Program: `C:\Windows\System32\cloudflared.exe`
   - Arguments: `tunnel --config C:\cloudflare-tunnel\config.yml run olympic-hr`
   - Start in: `C:\cloudflare-tunnel`
6. OK → Enter password

---

## Keep VM Running

Since this VM is your server:

### Inside the VM:
1. Control Panel → Power Options → Edit Plan Settings
2. Set **"Turn off display"** to **Never**
3. Set **"Put computer to sleep"** to **Never**
4. **Disable Hibernate**:
   ```cmd
   powercfg /hibernate off
   ```

### In your VM software:
- VMware: VM → Settings → Options → Disable "Suspend when VM is idle"
- VirtualBox: Machine → Settings → System → Motherboard → Uncheck "Enable EFI"
- Hyper-V: Settings → Automatic Stop Action → Shut down (not Hibernate)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Tunnel not found" in cloudflared | Check credentials file path in config.yml |
| "localhost:11434 refused" | Ollama not running. Check system tray for Ollama icon. |
| "localhost:5678 refused" | n8n container stopped. Run `docker start n8n` |
| URL changes on restart | Use your own domain, or buy cheap one ($3/year) |
| VM has no internet | Check VM network adapter is Bridged or NAT |
| Streamlit shows "Not reachable" | Check Cloudflare tunnel is running (`nssm status CloudflareTunnel`) |

---

## Quick Status Check Commands

```cmd
# Check all services
curl http://localhost:11434/api/tags
curl http://localhost:5678/healthz

# Check tunnel
sc query CloudflareTunnel

# Restart if needed
nssm restart CloudflareTunnel
docker restart n8n
```

---

## Cost

Everything is **FREE**:
- Windows 10 VM: Use evaluation ISO or existing license
- Ollama: Free
- Docker Desktop: Free (personal use)
- n8n: Free
- Cloudflare Tunnel: Free forever
- Neon PostgreSQL: Free (500 MB)
- Streamlit Cloud: Free
