# Windows Native Setup Guide — Ollama + n8n + Cloudflare Tunnel
# Run everything directly on your Windows PC (no VM needed)

## Architecture

```
Streamlit Cloud (Dashboard)
         │
         ▼
Cloudflare Tunnel (HTTPS, free)
         │
         ▼
Your Windows PC → Ollama (native) + n8n (Docker or Node.js)
```

## Why Windows Native?
- Easier than VMware — no VM overhead
- Ollama has official Windows support
- n8n runs fine on Windows via Docker Desktop
- Same Cloudflare Tunnel for secure public access

---

## Step 1: Install Ollama (Windows Native)

1. Go to **[ollama.com](https://ollama.com)**
2. Click **"Download for Windows"**
3. Run the installer → Follow prompts → Ollama starts automatically
4. **Verify**: Open PowerShell and run:
   ```powershell
   ollama --version
   ```

5. **Pull the model** (takes 5-15 min, ~5 GB download):
   ```powershell
   ollama pull qwen3:8b-q4_K_M
   ```

6. **Test Ollama**:
   ```powershell
   curl http://localhost:11434/api/tags
   ```
   Should show JSON with your model.

**Ollama is now running on Windows** and will auto-start with Windows.

---

## Step 2: Install Docker Desktop (for n8n)

n8n runs best in Docker on Windows.

1. Go to **[docker.com](https://www.docker.com)**
2. Click **"Download Docker Desktop"**
3. Run the installer
4. During setup:
   - **Use WSL 2**: Yes (recommended)
   - **Add shortcut**: Yes
5. **Restart** your PC if prompted
6. Open Docker Desktop, skip the sign-in (or create free account)

---

## Step 3: Start n8n via Docker

1. Create a folder for n8n data:
   ```powershell
   mkdir C:\n8n-data
   ```

2. Run n8n container:
   ```powershell
   docker run -d --name n8n `
     -p 5678:5678 `
     -v C:\n8n-data:/home/node/.n8n `
     -e N8N_BASIC_AUTH_ACTIVE=true `
     -e N8N_BASIC_AUTH_USER=admin `
     -e N8N_BASIC_AUTH_PASSWORD=changeme123 `
     n8nio/n8n:latest
   ```

3. **Verify n8n is running**:
   ```powershell
   curl http://localhost:5678/healthz
   ```
   Should return `{"status":"ok"}`

4. **View n8n UI** (optional, local only):
   - Open browser → `http://localhost:5678`
   - Login: `admin` / `changeme123`

---

## Step 4: Install Cloudflare Tunnel

This exposes your local Ollama + n8n to the internet with a public HTTPS URL.

### Step 4.1: Download cloudflared
1. Go to **[GitHub: cloudflared releases](https://github.com/cloudflare/cloudflared/releases/latest)**
2. Download `cloudflared-windows-amd64.exe`
3. Rename to `cloudflared.exe`
4. Move to `C:\Windows\System32\` (or any folder in your PATH)

### Step 4.2: Create a folder for Cloudflare config
```powershell
mkdir C:\cloudflare-tunnel
cd C:\cloudflare-tunnel
```

### Step 4.3: Authenticate
```powershell
cloudflared.exe tunnel login
```
- This opens a browser → Log in to Cloudflare (create free account if needed)
- Authorize → Certificate downloads automatically

### Step 4.4: Create the tunnel
```powershell
cloudflared.exe tunnel create olympic-hr
```
- This outputs a **tunnel ID** like: `1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p`
- **Copy this tunnel ID** — you'll need it

A credential file is created at:
```
C:\Users\YOURNAME\.cloudflared\1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p.json
```

### Step 4.5: Create config file
Create file `C:\cloudflare-tunnel\config.yml` with this content:

```yaml
tunnel: YOUR_TUNNEL_ID_HERE
credentials-file: C:\Users\YOURNAME\.cloudflared\YOUR_TUNNEL_ID_HERE.json

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

**Replace:**
- `YOUR_TUNNEL_ID_HERE` → your actual tunnel ID
- `YOURNAME` → your Windows username
- `yourdomain.com` → your actual domain (see Step 4.6)

### Step 4.6: DNS Options

**Option A: Use your own domain (recommended for permanence)**
1. Have a domain (any domain, can be cheap ~$3/year)
2. Point domain to Cloudflare nameservers
3. Run these commands to create DNS records:
   ```powershell
   cloudflared.exe tunnel route dns YOUR_TUNNEL_ID_HERE ollama.yourdomain.com
   cloudflared.exe tunnel route dns YOUR_TUNNEL_ID_HERE n8n.yourdomain.com
   ```

**Option B: Use free trycloudflare.com subdomain (URL changes on restart)**
- Skip the DNS step above
- The tunnel will give you a random URL like `https://random-words.trycloudflare.com`

### Step 4.7: Start the tunnel
```powershell
cd C:\cloudflare-tunnel
cloudflared.exe tunnel --config config.yml run olympic-hr
```

Keep this PowerShell window open. You'll see output like:
```
INF Connection registered connIndex=0
INF Updated to new configuration config=null
INF Registered tunnel connection
```

**Your public URL is now active.**

If using trycloudflare, the URL is printed at the top:
```
https://random-words.trycloudflare.com
```

---

## Step 5: Configure Streamlit Cloud Secrets

Go to your [Streamlit Cloud dashboard](https://share.streamlit.io/) → **Manage app → Secrets**:

```toml
# ── PostgreSQL (Neon) ─────────────────────────────────────────────────────
[postgresql]
host = "your-project.neon.tech"
port = "5432"
dbname = "neondb"
user = "neondb_owner"
password = "your-neon-password"

# ── Remote Ollama (Cloudflare Tunnel URL) ──────────────────────────────────
# If using your own domain:
OLLAMA_HOST = "https://ollama.yourdomain.com"
# If using trycloudflare (replace with your actual URL):
# OLLAMA_HOST = "https://random-words.trycloudflare.com"
OLLAMA_MODEL = "qwen3:8b-q4_K_M"

# ── Remote n8n (Cloudflare Tunnel URL) ─────────────────────────────────────
# If using your own domain:
N8N_HOST = "https://n8n.yourdomain.com"
# If using trycloudflare:
# N8N_HOST = "https://random-words.trycloudflare.com"

# ── GitHub Actions trigger ───────────────────────────────────────────────
[github]
token = "ghp_xxxxxxxxxxxxxxxxxxxx"
repo = "Riad154/Olympic-Resume-Ranking-"

# ── BDJobs credentials ───────────────────────────────────────────────────
[bdjobs]
username = "your_bdjobs_username"
password = "your_bdjobs_password"
```

**Click Save** → App restarts automatically.

---

## Step 6: Verify in Streamlit Cloud

Open your app → **Settings** page. You should see:
- **🟢 PostgreSQL** — Connected
- **🟢 Ollama** — 1 model(s) loaded
- **🟢 n8n** — Running

If any show 🔴:
- Check that Ollama is running: `curl http://localhost:11434/api/tags`
- Check that n8n is running: `curl http://localhost:5678/healthz`
- Check that Cloudflare tunnel is running (the PowerShell window must stay open)

---

## Step 7: Make Tunnel Run Automatically (Windows Service)

Right now the tunnel stops when you close PowerShell. Let's make it a Windows service.

### Option A: Use NSSM (easiest)

1. Download **NSSM** from [nssm.cc](https://nssm.cc/download)
2. Extract `nssm.exe` to `C:\Windows\System32\`
3. Install as a service:
   ```powershell
   nssm install CloudflareTunnel
   ```
4. In the GUI that opens:
   - **Path**: `C:\Windows\System32\cloudflared.exe`
   - **Startup directory**: `C:\cloudflare-tunnel`
   - **Arguments**: `tunnel --config C:\cloudflare-tunnel\config.yml run olympic-hr`
5. Click **Install service**
6. Start the service:
   ```powershell
   nssm start CloudflareTunnel
   ```
7. Set to auto-start:
   ```powershell
   nssm set CloudflareTunnel Start SERVICE_AUTO_START
   ```

Now the tunnel runs automatically when Windows boots.

### Option B: Use Windows Task Scheduler (no extra tools)

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Task** (not Basic Task)
3. **General** tab:
   - Name: `Cloudflare Tunnel`
   - Check: **Run whether user is logged on or not**
   - Check: **Run with highest privileges**
4. **Triggers** tab:
   - Click **New** → **At startup** → OK
5. **Actions** tab:
   - Click **New** → **Start a program**
   - Program: `C:\Windows\System32\cloudflared.exe`
   - Add arguments: `tunnel --config C:\cloudflare-tunnel\config.yml run olympic-hr`
   - Start in: `C:\cloudflare-tunnel`
6. **Conditions** tab:
   - Uncheck **Start only if on AC power** (if you want it to run on battery)
7. Click **OK** → Enter your Windows password

---

## Keep Your PC Running

Since this is your server:

1. **Disable Sleep**:
   - Control Panel → Power Options → Edit Plan Settings
   - Set **"Put computer to sleep"** to **"Never"**

2. **Disable Hibernate**:
   - Open PowerShell as Administrator:
   ```powershell
   powercfg /hibernate off
   ```

3. **Auto-start Ollama**:
   - Ollama already auto-starts with Windows by default
   - Check: Task Manager → Startup tab → Ollama should be "Enabled"

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Ollama not found" in PowerShell | Ollama installer should add to PATH. Restart PowerShell or PC. |
| "Docker not found" | Docker Desktop not in PATH. Use Docker Desktop's PowerShell or restart. |
| Tunnel URL changes on restart | Use your own domain, or buy a cheap one ($3/year on Namecheap) |
| High latency | Expected — traffic goes Streamlit Cloud → Cloudflare → Your PC. Still usable. |
| n8n container keeps stopping | Check Docker Desktop → Containers. May be port conflict. Change `-p 5678:5678` to `-p 5679:5678` and update secrets. |
| Ollama uses too much RAM | Close other apps. Ollama needs ~6 GB RAM for qwen3:8b. |

---

## Cost Summary

| Component | Cost |
|-----------|------|
| Ollama (Windows) | **Free** |
| Docker Desktop | **Free** (personal use) |
| n8n | **Free** (open source) |
| Cloudflare Tunnel | **Free** forever |
| PostgreSQL (Neon) | **Free** (500 MB) |
| Streamlit Cloud | **Free** |
| **Total** | **$0** |

---

## Quick Reference Commands

### Check all services locally
```powershell
# Ollama
curl http://localhost:11434/api/tags

# n8n
curl http://localhost:5678/healthz

# Tunnel status (if running as service)
Get-Service CloudflareTunnel
```

### Restart services
```powershell
# Restart Ollama
Restart-Service ollama

# Restart n8n
docker restart n8n

# Restart tunnel
Restart-Service CloudflareTunnel
```

### View logs
```powershell
# Ollama logs
Get-Content $env:LOCALAPPDATA\Ollama\logs\server.log -Tail 50

# n8n logs
docker logs n8n --tail 50

# Tunnel logs (if using NSSM)
nssm log CloudflareTunnel
```
