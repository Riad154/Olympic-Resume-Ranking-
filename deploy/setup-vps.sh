#!/bin/bash
# setup-vps.sh — One-command setup for Ollama + n8n on Ubuntu/Debian VPS
# Run as root or with sudo:  bash setup-vps.sh

set -e

echo "=== Olympic HR Platform — Cloud VPS Setup ==="

# ── Update system ───────────────────────────────────────────────────────────
apt-get update
apt-get install -y curl ca-certificates gnupg lsb-release git ufw

# ── Install Docker ────────────────────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "[+] Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ${SUDO_USER:-$USER}
    echo "[!] Docker installed. You may need to log out and back in for group changes."
else
    echo "[*] Docker already installed"
fi

# ── Install Docker Compose plugin ───────────────────────────────────────────
if ! docker compose version &> /dev/null; then
    echo "[+] Installing Docker Compose plugin..."
    apt-get install -y docker-compose-plugin
else
    echo "[*] Docker Compose already installed"
fi

# ── Clone/pull app repo (optional — if deploying from GitHub) ───────────────
# PROJECT_DIR="/opt/olympic-hr"
# if [ -d "$PROJECT_DIR/.git" ]; then
#     git -C "$PROJECT_DIR" pull
# else
#     git clone https://github.com/Riad154/Olympic-Resume-Ranking-.git "$PROJECT_DIR"
# fi

# ── Firewall: restrict Ollama/n8n to your IP only ────────────────────────────
echo "[+] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh

# If using nginx reverse proxy (recommended), only open 80/443:
ufw allow 80/tcp
ufw allow 443/tcp

# If exposing Ollama/n8n directly (NOT recommended without VPN/basic auth):
# ufw allow 11434/tcp
# ufw allow 5678/tcp

ufw --force enable
echo "[!] Firewall active. Ports 80/443 open. SSH allowed."

# ── Create htpasswd for nginx basic auth ────────────────────────────────────
HTPASSWD_FILE="./nginx/.htpasswd"
if [ ! -f "$HTPASSWD_FILE" ]; then
    echo "[+] Creating basic auth password file..."
    mkdir -p ./nginx
    read -sp "Enter password for 'admin' user: " ADMIN_PASS
    echo
    docker run --rm httpd:alpine htpasswd -nb "admin" "$ADMIN_PASS" > "$HTPASSWD_FILE"
    chmod 600 "$HTPASSWD_FILE"
    echo "[*] htpasswd created at $HTPASSWD_FILE"
fi

# ── Pull model after Ollama starts ──────────────────────────────────────────
echo "[+] Starting services with docker compose..."
docker compose -f docker-compose-with-nginx.yml up -d

echo "[+] Waiting for Ollama to be ready..."
sleep 10

MODEL="qwen3:8b-q4_K_M"
echo "[+] Pulling Ollama model: $MODEL ..."
docker compose -f docker-compose-with-nginx.yml exec ollama ollama pull "$MODEL"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Services should now be running:"
echo "  Ollama:  http://YOUR_VPS_IP:11434  (or via nginx /ollama/)"
echo "  n8n:     http://YOUR_VPS_IP:5678    (or via nginx /n8n/)"
echo ""
echo "Next steps:"
echo "  1. Point a domain to this VPS IP"
echo "  2. Get TLS cert: certbot certonly --standalone -d your-domain.com"
echo "  3. Update nginx.conf server_name and mount certs"
echo "  4. Set Streamlit Cloud secrets: OLLAMA_HOST, N8N_HOST, PG_*"
echo ""
