#!/usr/bin/env bash
# MammothOS Deploy Script for DigitalOcean Droplet
# This script is executed by GitHub Actions deploy workflow after SSH into the droplet.
#
# Usage:
#   bash /opt/mammothos/mammoth_intro_ai/scripts/deploy-droplet.sh
#
# Expected environment:
#   - Working directory: /opt/mammothos/mammoth_intro_ai
#   - User has sudo access for systemctl and file operations
#   - Backend service: mammothos (systemd unit)
#   - Frontend output: /var/www/mammothos-ui

set -euo pipefail

APP_ROOT="/opt/mammothos/mammoth_intro_ai"
UI_BUILD_DIR="${APP_ROOT}/ui/mad-architecht-command-center/dist"
UI_DEPLOY_DIR="/var/www/mammothos-ui"
BACKEND_SERVICE="mammothos"
NGINX_SERVICE="nginx"

echo "=========================================="
echo "MammothOS Deploy: Starting"
echo "=========================================="

cd "$APP_ROOT"

# Step 1: Pull latest main
echo ""
echo "[1/6] Pulling latest main branch..."
git fetch origin
git checkout main
git pull --ff-only origin main

# Step 2: Build frontend
echo ""
echo "[2/6] Building frontend..."
cd "${APP_ROOT}/ui/mad-architecht-command-center"
npm install --prefer-offline --no-audit
npm run build

# Step 3: Deploy frontend
echo ""
echo "[3/6] Deploying frontend to ${UI_DEPLOY_DIR}..."
sudo mkdir -p "$UI_DEPLOY_DIR"
sudo rm -rf "${UI_DEPLOY_DIR:?}/"* 2>/dev/null || true
sudo cp -r "${UI_BUILD_DIR}/." "$UI_DEPLOY_DIR/"
echo "✓ Frontend deployed"

# Step 4: Restart backend
echo ""
echo "[4/6] Restarting backend service '${BACKEND_SERVICE}'..."
cd "$APP_ROOT"
sudo systemctl restart "$BACKEND_SERVICE"
sleep 2
if sudo systemctl is-active --quiet "$BACKEND_SERVICE"; then
  echo "✓ Backend restarted and running"
else
  echo "✗ Backend failed to start. Run: sudo systemctl status ${BACKEND_SERVICE}"
  exit 1
fi

# Step 5: Reload nginx
echo ""
echo "[5/6] Testing nginx config..."
sudo nginx -t
echo ""
echo "[6/6] Reloading nginx..."
sudo systemctl reload "$NGINX_SERVICE"
sleep 1
if sudo systemctl is-active --quiet "$NGINX_SERVICE"; then
  echo "✓ Nginx reloaded and running"
else
  echo "✗ Nginx failed. Run: sudo systemctl status ${NGINX_SERVICE}"
  exit 1
fi

echo ""
echo "=========================================="
echo "✓ Deploy complete!"
echo "=========================================="
echo ""
echo "Frontend: ${UI_DEPLOY_DIR}"
echo "Backend:  ${BACKEND_SERVICE} (systemd)"
echo "Nginx:    ${NGINX_SERVICE} (systemd)"
echo ""