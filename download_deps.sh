#!/bin/bash
# =============================================================================
# دانلود dependencies روی لپ‌تاپ (آنلاین) برای نصب آفلاین روی سرور
# اجرا: bash download_deps.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR_DIR="$SCRIPT_DIR/vendor"

echo "╔══════════════════════════════════════════╗"
echo "║    دانلود dependencies (آنلاین)          ║"
echo "╚══════════════════════════════════════════╝"

command -v python3 &>/dev/null || { echo "python3 یافت نشد"; exit 1; }

mkdir -p "$VENDOR_DIR"

echo "[*] دانلود wheel ها برای Python 3.6 / Linux / x86_64..."
pip3 download \
    --python-version 36 \
    --platform linux_x86_64 \
    --only-binary=:all: \
    --dest "$VENDOR_DIR" \
    -r "$SCRIPT_DIR/requirements.txt" \
    || {
        echo "[!] --only-binary شکست خورد، تلاش با source packages..."
        pip3 download \
            --dest "$VENDOR_DIR" \
            -r "$SCRIPT_DIR/requirements.txt"
    }

echo ""
echo "[✓] فایل‌های دانلود شده:"
ls -lh "$VENDOR_DIR"
echo ""
echo "[✓] تعداد: $(ls "$VENDOR_DIR" | wc -l) فایل"
echo ""
echo "حالا پوشه vendor/ را به سرور منتقل کنید و install.sh را اجرا کنید."
