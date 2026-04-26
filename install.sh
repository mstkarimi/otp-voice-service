#!/bin/bash
# =============================================================================
# OTP Voice Call Service - Installer
# سیستم: CentOS / Issabel PBX
# اجرا: bash install.sh [--yes]
# =============================================================================

set -euo pipefail

INSTALL_DIR="/opt/otp-service"
CONFIG_DIR="/etc/otp-service"
LOG_DIR="/var/log/otp-service"
DATA_DIR="/var/lib/otp-service"
SOUNDS_DIR="/var/lib/asterisk/sounds/otp"
SERVICE_USER="otp-service"
SERVICE_NAME="otp-service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python 3.8 است اما pip3 هم روی 3.8 است
PYTHON_BIN="/usr/local/bin/python3.8"
if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="$(which python3.8 2>/dev/null || which python3 2>/dev/null)"
fi

AUTO_YES=false
if [[ "${1:-}" == "--yes" ]]; then
    AUTO_YES=true
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }

confirm() {
    if $AUTO_YES; then return 0; fi
    read -r -p "$1 [y/N] " ans
    [[ "${ans,,}" == "y" ]]
}

# =============================================================================
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║    OTP Voice Call Service - Installer        ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# --- بررسی root ---
[[ $EUID -eq 0 ]] || error "این اسکریپت باید با root اجرا شود (sudo bash install.sh)"

# --- بررسی prerequisites ---
log "بررسی پیش‌نیازها..."

command -v "$PYTHON_BIN" &>/dev/null || error "python3.8 یافت نشد (مسیر: $PYTHON_BIN)"
PYTHON_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
log "Python: $PYTHON_VERSION ($PYTHON_BIN)"

command -v asterisk &>/dev/null || error "asterisk یافت نشد"
ASTERISK_VERSION=$(asterisk -V 2>/dev/null | head -1)
log "Asterisk: $ASTERISK_VERSION"

command -v systemctl &>/dev/null || error "systemctl یافت نشد"

if ! command -v sox &>/dev/null; then
    warn "sox یافت نشد - تبدیل فرمت صدا انجام نخواهد شد"
fi

# --- تایید نصب ---
echo ""
warn "موارد زیر روی سرور تغییر می‌کنند:"
echo "  • ایجاد user: $SERVICE_USER"
echo "  • نصب در: $INSTALL_DIR"
echo "  • کانفیگ در: $CONFIG_DIR"
echo "  • لاگ در: $LOG_DIR"
echo "  • Append به: /etc/asterisk/extensions_custom.conf"
echo "  • Append به: /etc/asterisk/manager_custom.conf"
echo "  • نصب صداها در: $SOUNDS_DIR"
echo ""
confirm "ادامه می‌دهید؟" || { echo "نصب لغو شد."; exit 0; }

# =============================================================================
# STEP 1: Backup
# =============================================================================
log "گرفتن backup از کانفیگ‌های Asterisk..."
BACKUP_DIR="/root/otp-backup-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

for f in /etc/asterisk/extensions_custom.conf /etc/asterisk/manager_custom.conf; do
    [[ -f "$f" ]] && cp "$f" "$BACKUP_DIR/" && log "Backup: $f → $BACKUP_DIR/"
done
log "Backup در $BACKUP_DIR ذخیره شد"

# =============================================================================
# STEP 2: ساخت user سرویس
# =============================================================================
log "ساخت user سرویس..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /sbin/nologin "$SERVICE_USER"
    log "User $SERVICE_USER ساخته شد"
else
    log "User $SERVICE_USER از قبل وجود دارد"
fi

# =============================================================================
# STEP 3: ساخت پوشه‌ها
# =============================================================================
log "ساخت پوشه‌های مورد نیاز..."
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR" "$DATA_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR" "$DATA_DIR"
chmod 750 "$LOG_DIR" "$DATA_DIR" "$CONFIG_DIR"

# =============================================================================
# STEP 4: کپی سورس‌کد
# =============================================================================
log "کپی سورس‌کد..."
cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/src"

# =============================================================================
# STEP 5: virtualenv و نصب dependencies
# =============================================================================
log "ساخت virtualenv با Python 3.8..."
rm -rf "$INSTALL_DIR/venv"
"$PYTHON_BIN" -m venv --without-pip "$INSTALL_DIR/venv" \
    || error "ساخت venv شکست خورد"

# bootstrap pip داخل venv
log "Bootstrap pip در venv..."
curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py 2>/dev/null \
    || "$PYTHON_BIN" -c "
import urllib.request
urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/tmp/get-pip.py')
" 2>/dev/null \
    || {
        # اگر اینترنت نداشت، pip خود سیستم را کپی کن
        warn "دانلود get-pip.py ممکن نبود، از pip سیستم استفاده می‌شود"
        cp "$(which pip3)" "$INSTALL_DIR/venv/bin/pip" 2>/dev/null || true
    }

if [[ -f /tmp/get-pip.py ]]; then
    "$INSTALL_DIR/venv/bin/python" /tmp/get-pip.py --no-index \
        --find-links="$SCRIPT_DIR/vendor" 2>/dev/null \
    || "$INSTALL_DIR/venv/bin/python" /tmp/get-pip.py 2>/dev/null \
    || warn "get-pip.py اجرا نشد - ادامه با pip سیستم"
fi

# اگر pip در venv نیست، symlink بزن
if [[ ! -f "$INSTALL_DIR/venv/bin/pip" ]]; then
    PIP38=$(which pip3.8 2>/dev/null || which pip3 2>/dev/null)
    [[ -n "$PIP38" ]] && ln -sf "$PIP38" "$INSTALL_DIR/venv/bin/pip"
fi

log "نصب dependencies از vendor/ (آفلاین)..."
INSTALL_CMD="$INSTALL_DIR/venv/bin/pip"
if [[ ! -x "$INSTALL_CMD" ]]; then
    INSTALL_CMD="pip3"
fi

if [[ -d "$SCRIPT_DIR/vendor" ]] && ls "$SCRIPT_DIR/vendor"/*.whl &>/dev/null; then
    "$INSTALL_CMD" install --no-index \
        --find-links="$SCRIPT_DIR/vendor" \
        -r "$SCRIPT_DIR/requirements.txt" \
        --target="$INSTALL_DIR/lib" \
        || error "نصب dependencies شکست خورد"
else
    error "vendor/ خالی است"
fi
log "Dependencies نصب شدند"

# =============================================================================
# STEP 6: نصب صداها (منطق هوشمند)
# =============================================================================
log "راه‌اندازی فایل‌های صوتی..."
USE_SYSTEM_SOUNDS=false

check_existing_sounds() {
    for search_path in "/var/lib/asterisk/sounds/fa/digits" "/usr/share/asterisk/sounds/fa/digits"; do
        if [[ -d "$search_path" ]] && ls "$search_path"/*.{gsm,wav,ulaw} &>/dev/null 2>&1; then
            FOUND_SOUNDS_PATH="$search_path"
            return 0
        fi
    done
    return 1
}

if check_existing_sounds; then
    log "صداهای فارسی سیستمی یافت شد در: $FOUND_SOUNDS_PATH"
    missing=false
    for i in {0..9}; do
        if ! ls "$FOUND_SOUNDS_PATH/${i}".{gsm,wav,ulaw} &>/dev/null 2>&1; then
            warn "فایل عدد $i در صداهای سیستمی ناقص است"
            missing=true
            break
        fi
    done
    if ! $missing; then
        USE_SYSTEM_SOUNDS=true
        log "از صداهای سیستمی Asterisk استفاده می‌شود (SayDigits)"
    fi
fi

mkdir -p "$SOUNDS_DIR/digits"

if $USE_SYSTEM_SOUNDS; then
    # فقط فایل‌های عبارات پروژه را کپی کن
    for f in otp-intro.wav otp-repeat.wav otp-goodbye.wav otp-error.wav; do
        [[ -f "$SCRIPT_DIR/sounds/$f" ]] && cp "$SCRIPT_DIR/sounds/$f" "$SOUNDS_DIR/"
    done
else
    # همه فایل‌های صوتی را کپی کن
    cp "$SCRIPT_DIR/sounds/"*.wav "$SOUNDS_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/sounds/digits/"*.wav "$SOUNDS_DIR/digits/" 2>/dev/null || true

    # تبدیل به gsm برای کارایی بهتر
    if command -v sox &>/dev/null; then
        log "تبدیل فایل‌های صوتی به gsm..."
        for f in "$SOUNDS_DIR"/*.wav "$SOUNDS_DIR/digits/"*.wav; do
            [[ -f "$f" ]] && sox "$f" "${f%.wav}.gsm" 2>/dev/null && log "  تبدیل شد: ${f##*/}"
        done
    fi
fi

chown -R asterisk:asterisk "$SOUNDS_DIR"
chmod -R 755 "$SOUNDS_DIR"
log "فایل‌های صوتی نصب شدند در $SOUNDS_DIR"

# =============================================================================
# STEP 7: کانفیگ AMI
# =============================================================================
log "افزودن AMI user به manager_custom.conf..."
AMI_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(16))")

AMI_CONF="/etc/asterisk/manager_custom.conf"
touch "$AMI_CONF"

if grep -q "\[otp_service\]" "$AMI_CONF"; then
    warn "AMI user otp_service از قبل وجود دارد - skip"
else
    cat >> "$AMI_CONF" << EOF

; --- OTP Voice Call Service ---
[otp_service]
secret = ${AMI_SECRET}
deny = 0.0.0.0/0.0.0.0
permit = 127.0.0.1/255.255.255.255
read = call
write = originate,call
writetimeout = 5000
EOF
    log "AMI user otp_service اضافه شد"
fi

# =============================================================================
# STEP 8: Dialplan
# =============================================================================
log "افزودن dialplan به extensions_custom.conf..."
EXT_CONF="/etc/asterisk/extensions_custom.conf"
touch "$EXT_CONF"

if grep -q "\[otp-playback\]" "$EXT_CONF"; then
    warn "Dialplan otp-playback از قبل وجود دارد - skip"
else
    cat "$SCRIPT_DIR/asterisk/extensions_custom.conf" >> "$EXT_CONF"
    log "Dialplan اضافه شد"
fi

# =============================================================================
# STEP 9: Reload Asterisk (بدون restart)
# =============================================================================
log "Reload Asterisk (dialplan + manager)..."
asterisk -rx "dialplan reload" && log "  dialplan reload OK"
asterisk -rx "manager reload"  && log "  manager reload OK"

# =============================================================================
# STEP 10: تولید API Key و config.yaml
# =============================================================================
log "تولید API Key و کانفیگ..."
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
API_KEY_HASH=$("$INSTALL_DIR/venv/bin/python" -c "
from passlib.context import CryptContext
ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
print(ctx.hash('$API_KEY'))
")

SOUNDS_CONF_VALUE=$([ "$USE_SYSTEM_SOUNDS" = true ] && echo "true" || echo "false")

cat > "$CONFIG_DIR/config.yaml" << EOF
api:
  host: "0.0.0.0"
  port: 8080
  api_key_hash: "${API_KEY_HASH}"
  ip_whitelist: []

asterisk:
  host: "127.0.0.1"
  port: 5038
  username: "otp_service"
  secret: "${AMI_SECRET}"
  trunk: "90004455"
  caller_id: "90004455"
  call_timeout: 30
  reconnect_delay: 5

rate_limit:
  per_number_calls: 3
  per_number_window_minutes: 10
  max_concurrent_calls: 20
  hourly_limit: 500

sounds:
  base_path: "${SOUNDS_DIR}"
  use_system_digits: ${SOUNDS_CONF_VALUE}

logging:
  level: "INFO"
  dir: "${LOG_DIR}"
  max_bytes: 10485760
  backup_count: 5

database:
  path: "${DATA_DIR}/otp.db"
EOF

chmod 640 "$CONFIG_DIR/config.yaml"
chown root:"$SERVICE_USER" "$CONFIG_DIR/config.yaml"
log "config.yaml ساخته شد"

# =============================================================================
# STEP 11: Systemd Service
# =============================================================================
log "نصب systemd service..."
cp "$SCRIPT_DIR/systemd/otp-service.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"
log "Service نصب و راه‌اندازی شد"

# =============================================================================
# STEP 12: Health Check
# =============================================================================
log "Health check (۵ ثانیه صبر)..."
sleep 5

if curl -sf "http://127.0.0.1:8080/api/v1/health" &>/dev/null; then
    log "✅ سرویس آنلاین است"
else
    warn "سرویس هنوز در حال راه‌اندازی است - لاگ را بررسی کنید:"
    warn "  journalctl -u otp-service -n 20"
fi

# =============================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              نصب با موفقیت انجام شد!                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo -e "${YELLOW}⚠️  API KEY (یک بار نمایش داده می‌شود - ذخیره کنید!):${NC}"
echo ""
echo "  $API_KEY"
echo ""
echo "  لاگ سرویس:   journalctl -u otp-service -f"
echo "  وضعیت:       systemctl status otp-service"
echo "  health:       curl http://127.0.0.1:8080/api/v1/health"
echo "  backup:       $BACKUP_DIR"
echo ""
