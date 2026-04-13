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
deactivate || true

if command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
else
  PYTHON_BIN=""
fi

if [ -z "$PYTHON_BIN" ]; then
  if command -v apt-get >/dev/null 2>&1; then
    echo "Пробую установить python3.12 через apt..." >&2
    $SUDO apt-get update -y
    $SUDO apt-get install -y software-properties-common || true
    if command -v lsb_release >/dev/null 2>&1; then
      CODENAME="$(lsb_release -cs || true)"
      if [ "$CODENAME" = "jammy" ]; then
        $SUDO add-apt-repository -y ppa:deadsnakes/ppa
        $SUDO apt-get update -y
      fi
    fi
    $SUDO apt-get install -y python3.12 python3.12-venv
    PYTHON_BIN="python3.12"
  else
    echo "На сервере нет python3.12. Установи Python 3.12 и python3.12-venv, затем повтори." >&2
    exit 1
  fi
fi

$PYTHON_BIN -m venv .venv
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
