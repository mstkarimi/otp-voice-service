#!/bin/bash
# =============================================================================
# OTP Voice Call Service - Uninstaller / Rollback
# اجرا: bash uninstall.sh [--yes]
# =============================================================================

set -euo pipefail

SERVICE_NAME="otp-service"
INSTALL_DIR="/opt/otp-service"
CONFIG_DIR="/etc/otp-service"
LOG_DIR="/var/log/otp-service"
DATA_DIR="/var/lib/otp-service"
SOUNDS_DIR="/var/lib/asterisk/sounds/otp"
SERVICE_USER="otp-service"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }

AUTO_YES=false
[[ "${1:-}" == "--yes" ]] && AUTO_YES=true

[[ $EUID -eq 0 ]] || { echo "root مورد نیاز است"; exit 1; }

if ! $AUTO_YES; then
    echo ""
    warn "این اسکریپت OTP Voice Service را کاملاً حذف می‌کند"
    read -r -p "ادامه می‌دهید؟ [y/N] " ans
    [[ "${ans,,}" == "y" ]] || { echo "لغو شد."; exit 0; }
fi

# --- توقف سرویس ---
log "توقف و حذف سرویس..."
systemctl stop "$SERVICE_NAME"  2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

# --- حذف dialplan از extensions_custom.conf ---
log "حذف dialplan از extensions_custom.conf..."
EXT_CONF="/etc/asterisk/extensions_custom.conf"
if [[ -f "$EXT_CONF" ]]; then
    # حذف بلوک‌های otp از فایل
    python3 - "$EXT_CONF" << 'PYEOF'
import sys, re
path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()

# حذف context های otp
pattern = r'\n?; --- OTP.*?(?=\n\[|\Z)'
cleaned = re.sub(pattern, '', content, flags=re.DOTALL)
pattern2 = r'\n?\[otp-playback[^\]]*\].*?(?=\n\[|\Z)'
cleaned = re.sub(pattern2, '', cleaned, flags=re.DOTALL)

with open(path, 'w') as f:
    f.write(cleaned.strip() + '\n')
print("dialplan حذف شد")
PYEOF
    asterisk -rx "dialplan reload" 2>/dev/null && log "dialplan reload OK" || true
fi

# --- حذف AMI user از manager_custom.conf ---
log "حذف AMI user از manager_custom.conf..."
AMI_CONF="/etc/asterisk/manager_custom.conf"
if [[ -f "$AMI_CONF" ]]; then
    python3 - "$AMI_CONF" << 'PYEOF'
import sys, re
path = sys.argv[1]
with open(path, 'r') as f:
    content = f.read()
pattern = r'\n?; --- OTP.*?\n\[otp_service\].*?(?=\n\[|\Z)'
cleaned = re.sub(pattern, '', content, flags=re.DOTALL)
with open(path, 'w') as f:
    f.write(cleaned.strip() + '\n')
print("AMI user حذف شد")
PYEOF
    asterisk -rx "manager reload" 2>/dev/null && log "manager reload OK" || true
fi

# --- حذف فایل‌های صوتی ---
log "حذف فایل‌های صوتی..."
rm -rf "$SOUNDS_DIR"

# --- حذف نصب ---
log "حذف فایل‌های سرویس..."
rm -rf "$INSTALL_DIR"
rm -rf "$CONFIG_DIR"

# --- حذف لاگ‌ها (اختیاری) ---
if ! $AUTO_YES; then
    read -r -p "لاگ‌ها حذف شوند؟ [y/N] " ans
    [[ "${ans,,}" == "y" ]] && rm -rf "$LOG_DIR" && log "لاگ‌ها حذف شدند"
fi

# --- حذف database ---
if ! $AUTO_YES; then
    read -r -p "database حذف شود؟ [y/N] " ans
    [[ "${ans,,}" == "y" ]] && rm -rf "$DATA_DIR" && log "database حذف شد"
fi

# --- حذف user ---
if id "$SERVICE_USER" &>/dev/null; then
    userdel "$SERVICE_USER" 2>/dev/null || true
    log "User $SERVICE_USER حذف شد"
fi

echo ""
log "✅ حذف کامل انجام شد"
echo "  برای بازگشت به حالت قبل از backup استفاده کنید:"
echo "  ls /root/otp-backup-*"
