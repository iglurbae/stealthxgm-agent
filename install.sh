#!/usr/bin/env bash
# StealthXGM Agent — installer untuk VPS Linux (Ubuntu 20.04/22.04, headless).
# Menyiapkan: Python 3.9 + deps, Xvfb, kernel Chromium 152 (Chrome for
# Testing), systemd units untuk Xvfb + Local API, lalu verifikasi API.
#
# Pakai:  sudo bash install.sh [/opt/stealthxgm]
# Default target: /root/stealthxgm (sesuaikan argumen pertama bila perlu).
set -euo pipefail

TARGET="${1:-/root/stealthxgm}"
KERNEL_VERSION="152.0.7977.82"
KERNEL_URL="https://storage.googleapis.com/chrome-for-testing-public/${KERNEL_VERSION}/linux64/chrome-linux64.zip"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== StealthXGM Agent installer =="
echo "Target: $TARGET"

# --- 1. Paket sistem ---------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  python3.9 python3.9-venv python3-pip \
  xvfb unzip curl wget ca-certificates \
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
  libgbm1 libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 \
  fonts-liberation fonts-noto-color-emoji

# --- 2. Salin kode ------------------------------------------------------------
mkdir -p "$TARGET"
# Salin semua kecuali artefak runtime/build yang tidak boleh ikut.
rsync -a --delete \
  --exclude "browser_profiles/" --exclude "kernels/" --exclude "dist/" \
  --exclude "__pycache__/" --exclude "*.pyc" --exclude ".git/" \
  --exclude "gui/data/" \
  "$SRC_DIR"/ "$TARGET"/

# --- 3. Dependensi Python ------------------------------------------------------
python3.9 -m pip install --upgrade pip >/dev/null
python3.9 -m pip install -r "$TARGET/requirements.txt"

# --- 4. Kernel Chromium (Chrome for Testing) -----------------------------------
KDIR="$TARGET/kernels/$KERNEL_VERSION"
if [ ! -x "$KDIR/chrome-linux64/chrome" ]; then
  echo "Mengunduh kernel Chromium $KERNEL_VERSION ..."
  mkdir -p "$KDIR"
  TMP_ZIP="$(mktemp /tmp/cft-XXXXXX.zip)"
  curl -fL "$KERNEL_URL" -o "$TMP_ZIP"
  unzip -q -o "$TMP_ZIP" -d "$KDIR"
  rm -f "$TMP_ZIP"
  chmod +x "$KDIR/chrome-linux64/chrome"
fi

# Registry kernel (dibaca launcher; path absolut ke target)
mkdir -p "$TARGET/gui/data"
cat > "$TARGET/gui/data/kernels.json" <<EOF
{
  "default": "chromium-$KERNEL_VERSION",
  "kernels": {
    "chromium-$KERNEL_VERSION": {
      "id": "chromium-$KERNEL_VERSION",
      "name": "Chromium $KERNEL_VERSION",
      "version": "$KERNEL_VERSION",
      "engine": "chromium",
      "path": "$KDIR/chrome-linux64/chrome",
      "source": "cft",
      "download_url": "$KERNEL_URL"
    }
  }
}
EOF

# --- 5. systemd units ------------------------------------------------------------
cat > /etc/systemd/system/xvfb.service <<'EOF'
[Unit]
Description=Xvfb :99 (display StealthXGM)
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x800x24
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/stealthxgm-api.service <<EOF
[Unit]
Description=StealthXGM local API :50325
After=network.target xvfb.service

[Service]
Type=simple
WorkingDirectory=$TARGET
Environment=DISPLAY=:99
ExecStart=/usr/bin/python3.9 gui/local_api.py --port 50325
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable xvfb stealthxgm-api
systemctl restart xvfb
sleep 2
systemctl restart stealthxgm-api

# --- 6. Verifikasi ----------------------------------------------------------------
echo "Menunggu API ..."
for i in $(seq 1 20); do
  if curl -sf "http://127.0.0.1:50325/api/v1/status" >/dev/null; then
    echo "API OK: http://127.0.0.1:50325/api/v1/status"
    curl -s "http://127.0.0.1:50325/api/v1/status"; echo
    echo "== Selesai. StealthXGM Agent jalan di $TARGET =="
    exit 0
  fi
  sleep 2
done

echo "API belum merespons. Cek: journalctl -u stealthxgm-api -n 50" >&2
exit 1
