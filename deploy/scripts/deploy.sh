#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/messgo}"
REPO_URL="${REPO_URL:-https://github.com/iseroot/messgo.git}"
TARGET_REF="${1:-main}"

if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
fi

if [ ! -d "$APP_DIR/.git" ]; then
  $SUDO mkdir -p "$APP_DIR"
  $SUDO chown -R "$USER":"$USER" "$APP_DIR"
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
git fetch --all --tags
git checkout "$TARGET_REF"

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

if [ -f deploy/systemd/messgo.service ]; then
  $SUDO cp deploy/systemd/messgo.service /etc/systemd/system/messgo.service
fi
if [ -f deploy/Caddyfile ]; then
  $SUDO cp deploy/Caddyfile /etc/caddy/Caddyfile
fi

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now messgo.service
$SUDO systemctl restart messgo.service

if $SUDO systemctl list-unit-files | grep -q '^caddy'; then
  $SUDO systemctl restart caddy.service
fi

curl -fsS http://127.0.0.1:8000/health >/dev/null
echo "deploy ok"
