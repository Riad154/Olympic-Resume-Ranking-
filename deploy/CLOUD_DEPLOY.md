# Cloud Deployment Guide — Olympic HR Intelligence Platform

This guide walks you through deploying Ollama, n8n, and PostgreSQL so your Streamlit Cloud app can use all services remotely.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Streamlit Cloud │────▶│  Neon Postgres  │     │   Your VPS      │
│   (Dashboard)    │     │   (Database)    │     │                 │
└─────────────────┘     └─────────────────┘     │  ┌───────────┐  │
                                                │  │  Ollama   │  │
                                                │  │  (LLM)    │  │
                                                │  └───────────┘  │
                                                │  ┌───────────┐  │
                                                │  │    n8n    │  │
                                                │  │ (Workflow)│  │
                                                │  └───────────┘  │
                                                └─────────────────┘
```

---

## Step 1: PostgreSQL (Neon — Free)

1. Go to [neon.tech](https://neon.tech) and sign up
2. Create a new project → copy the connection string
3. In Streamlit Cloud: **App → Settings → Secrets**, add:
   ```toml
   [postgresql]
   host = "your-project.neon.tech"
   port = "5432"
   dbname = "neondb"
   user = "neondb_owner"
   password = "your-neon-password"
   ```

---

## Step 2: VPS for Ollama + n8n

### Recommended VPS Options

| Provider | Specs | Cost | Link |
|---|---|---|---|
| **Oracle Cloud** | 4 ARM CPU, 24 GB RAM | **Free forever** | [cloud.oracle.com](https://cloud.oracle.com) |
| **Hetzner CX21** | 2 vCPU, 4 GB RAM | ~$5/mo | [hetzner.com](https://hetzner.com) |
| **DigitalOcean** | 2 vCPU, 4 GB RAM | ~$6/mo | [digitalocean.com](https://digitalocean.com) |

**Note:** Ollama needs at least 4 GB RAM for `qwen3:8b-q4_K_M`. Oracle Cloud Free Tier is the best zero-cost option.

### Quick Setup (Ubuntu)

1. **SSH into your VPS** and clone the repo:
   ```bash
   git clone https://github.com/Riad154/Olympic-Resume-Ranking-.git
   cd Olympic-Resume-Ranking-/deploy
   ```

2. **Run the setup script**:
   ```bash
   sudo bash setup-vps.sh
   ```
   This installs Docker, Docker Compose, sets up the firewall, and starts Ollama + n8n.

3. **Pull the AI model** (after Ollama is running):
   ```bash
   docker compose exec ollama ollama pull qwen3:8b-q4_K_M
   ```

---

## Step 3: Configure Streamlit Cloud Secrets

In Streamlit Cloud dashboard → **Manage app → Secrets**, add:

```toml
# ── PostgreSQL ─────────────────────────────────────────────────────────────
[postgresql]
host = "your-project.neon.tech"
port = "5432"
dbname = "neondb"
user = "neondb_owner"
password = "your-neon-password"

# ── Remote Ollama (your VPS IP) ──────────────────────────────────────────────
OLLAMA_HOST = "http://YOUR_VPS_IP:11434"
OLLAMA_MODEL = "qwen3:8b-q4_K_M"

# ── Remote n8n (your VPS IP) ───────────────────────────────────────────────
N8N_HOST = "http://YOUR_VPS_IP:5678"

# ── GitHub (for BDJobs sync) ───────────────────────────────────────────────
[github]
token = "ghp_xxxxxxxxxxxxxxxxxxxx"
repo = "Riad154/Olympic-Resume-Ranking-"

# ── BDJobs ─────────────────────────────────────────────────────────────────
[bdjobs]
username = "your_bdjobs_username"
password = "your_bdjobs_password"
```

**Important:** Replace `YOUR_VPS_IP` with your actual VPS public IP address.

---

## Step 4: Verify in Settings Page

Open your Streamlit Cloud app → **Settings** page. You should see:

- **🟢 PostgreSQL** — Connected
- **🟢 Ollama** — 1 model(s) loaded
- **🟢 n8n** — Running

If any show 🔴, check the secrets and VPS firewall.

---

## Optional: Secure with nginx + TLS (Recommended)

Exposing Ollama/n8n directly on the internet is risky. Use nginx with basic auth:

1. **Get a domain** (e.g., `hr-api.yourcompany.com`)
2. **Point the domain** to your VPS IP
3. **Get TLS certificate**:
   ```bash
   sudo apt install certbot
   sudo certbot certonly --standalone -d hr-api.yourcompany.com
   ```
4. **Create password file**:
   ```bash
   cd deploy/nginx
   docker run --rm httpd:alpine htpasswd -nb admin YOUR_STRONG_PASSWORD > .htpasswd
   chmod 600 .htpasswd
   ```
5. **Update nginx.conf**: Replace `server_name _;` with `server_name hr-api.yourcompany.com;`
6. **Update docker-compose-with-nginx.yml**: Uncomment the Let's Encrypt cert mount lines
7. **Start with nginx**:
   ```bash
   docker compose -f docker-compose-with-nginx.yml up -d
   ```
8. **Update Streamlit secrets** to use the domain with auth:
   ```toml
   OLLAMA_HOST = "https://admin:YOUR_STRONG_PASSWORD@hr-api.yourcompany.com/ollama"
   N8N_HOST = "https://admin:YOUR_STRONG_PASSWORD@hr-api.yourcompany.com/n8n"
   ```

---

## Firewall Rules (Direct VPS exposure)

If NOT using nginx, restrict Ollama/n8n ports to your Streamlit Cloud app only:

```bash
# Allow SSH
ufw allow 22/tcp

# Allow HTTP/HTTPS (for nginx)
ufw allow 80/tcp
ufw allow 443/tcp

# If exposing directly (NOT recommended), restrict by IP:
# ufw allow from YOUR_STREAMLIT_CLOUD_IP to any port 11434
# ufw allow from YOUR_STREAMLIT_CLOUD_IP to any port 5678

ufw enable
```

> **Note:** Streamlit Cloud IPs change. Use nginx with basic auth instead.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| "Not reachable" for Ollama/n8n | Check VPS firewall (`ufw status`). Ensure ports are open. |
| "Not configured" for PostgreSQL | Fill in all `[postgresql]` fields in Streamlit secrets. |
| Model shows 0 loaded | Run `docker compose exec ollama ollama pull qwen3:8b-q4_K_M` |
| AI ranking times out | Ollama on CPU is slow. Use Oracle Cloud (4 CPU ARM) or a GPU instance. |
| n8n not accessible | Check `docker compose logs n8n` for startup errors. |

---

## Cost Summary

| Service | Provider | Monthly Cost |
|---|---|---|
| Streamlit Cloud | Streamlit | **Free** |
| PostgreSQL | Neon | **Free** (up to 500 MB) |
| Ollama + n8n | Oracle Cloud | **Free** (ARM instance) |
| **Total** | | **$0/month** |

If Oracle Cloud is unavailable, Hetzner CX21 (~$5/mo) is the cheapest paid option.
