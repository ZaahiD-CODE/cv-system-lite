#!/bin/bash
set -eo pipefail

echo "========================================"
echo "  CV System - Installation"
echo "========================================"

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Error: this step requires root. Run with sudo or as root."
        exit 1
    fi
}

echo ""
echo "[1/6] Creating virtual environment..."
if ! command -v python3 &>/dev/null; then
    echo "  python3 not found, installing..."
    check_root
    apt-get update -qq && apt-get install -y -qq python3 python3-pip
fi

if ! python3 -m venv --help &>/dev/null 2>&1; then
    echo "  python3-venv not found, installing..."
    check_root
    apt-get update -qq && apt-get install -y -qq python3-venv
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo ""
echo "[2/6] Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -r web/requirements.txt -q

echo ""
echo "[3/6] Detecting GPU..."
python3 -c "
import torch
if torch.cuda.is_available():
    print(f'GPU found: {torch.cuda.get_device_name(0)}')
    print(f'Memory: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB')
else:
    print('No NVIDIA GPU detected, using CPU')
"

echo ""
echo "[4/6] Downloading YOLO models..."
mkdir -p models
python3 -c "
from ultralytics import YOLO
import os

os.chdir('$PROJECT_DIR')
models = [
    'yolo12n.pt', 'yolo12s.pt', 'yolo12m.pt', 'yolo12l.pt', 'yolo12x.pt',
]

for m in models:
    path = os.path.join('models', m)
    if os.path.exists(path):
        print(f'  {m} - already exists')
    else:
        print(f'  {m} - downloading...')
        try:
            model = YOLO(m)
            if os.path.exists(m):
                os.replace(m, path)
            print(f'  {m} - done')
        except Exception as e:
            print(f'  {m} - failed: {e}')
"

echo ""
echo "[5/6] Initializing database and generating config..."
python3 -c "
from web.database import init_db
init_db()
print('Database initialized')
"

ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    ADMIN_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

    echo ""
    read -rp "Enter your domain (e.g. vision.example.com) [leave empty for localhost only]: " DOMAIN
    if [ -z "$DOMAIN" ]; then
        CORS_ORIGINS="http://localhost:8000"
        echo "No domain set — CORS will allow localhost only"
    else
        CORS_ORIGINS="https://$DOMAIN,http://localhost:8000"
        echo "CORS origins: $CORS_ORIGINS"
    fi

    cat > "$ENV_FILE" <<EOF
JWT_SECRET_KEY=$JWT_SECRET
CV_ADMIN_PASSWORD=$ADMIN_PASS
CORS_ORIGINS=$CORS_ORIGINS
EOF
    chmod 600 "$ENV_FILE"
    echo ""
    echo "Generated .env with secrets (chmod 600)"
    echo "Default login: admin / $ADMIN_PASS"
    echo "Save this password — it won't be shown again!"
else
    echo ".env already exists, skipping generation"
    echo "Default login: check CV_ADMIN_PASSWORD in .env"
fi

# Nginx + SSL setup
if [ -n "$DOMAIN" ]; then
    echo ""
    read -rp "Setup nginx reverse proxy + Let's Encrypt SSL for $DOMAIN? [Y/n]: " SETUP_NGINX
    SETUP_NGINX=${SETUP_NGINX:-Y}
    if [[ "$SETUP_NGINX" =~ ^[Yy]$ ]]; then
        check_root
        echo ""
        echo "[6/6] Configuring nginx + SSL..."

        if ! command -v nginx &>/dev/null; then
            echo "  Installing nginx..."
            apt-get update -qq && apt-get install -y -qq nginx
        fi

        if ! command -v certbot &>/dev/null; then
            echo "  Installing certbot..."
            apt-get install -y -qq certbot python3-certbot-nginx
        fi

        NGINX_CONF="/etc/nginx/sites-available/cv-system"

        cat > "$NGINX_CONF" <<NGINX
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
NGINX

        ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/cv-system
        rm -f /etc/nginx/sites-enabled/default

        nginx -t
        systemctl enable nginx
        systemctl start nginx || systemctl reload nginx

        echo "  Requesting SSL certificate for $DOMAIN..."
        certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect

        SERVICE_FILE="/etc/systemd/system/cv-system.service"
        cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=CV System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/run_web.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

        systemctl daemon-reload
        systemctl enable cv-system
        systemctl start cv-system

        echo ""
        echo "  Nginx configured: https://$DOMAIN"
        echo "  SSL auto-renew: certbot renew --quiet"
        echo "  Service: systemctl status cv-system"
    else
        echo "Skipping nginx setup"
    fi
fi

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
if [ -n "$DOMAIN" ] && [[ "$SETUP_NGINX" =~ ^[Yy]$ ]]; then
    echo "Web interface: https://$DOMAIN"
    echo "Manage: systemctl {start,stop,restart,status} cv-system"
else
    echo "Start the server:"
    echo "  source venv/bin/activate"
    echo "  python3 run_web.py"
    echo ""
    echo "Web interface: http://localhost:8000"
fi
