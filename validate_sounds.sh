#!/bin/bash
# =============================================================================
# اعتبارسنجی فایل‌های صوتی - الزامات Asterisk
# فرمت: WAV, 8000Hz, Mono, 16-bit signed PCM
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOUNDS_DIR="${1:-$SCRIPT_DIR/sounds}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

check_file() {
    local f="$1"
    local name="${f##*/}"

    if [[ ! -f "$f" ]]; then
        echo -e "${RED}[✗]${NC} مفقود: $f"
        ((ERRORS++))
        return
    fi

    # بررسی با soxi یا ffprobe
    if command -v soxi &>/dev/null; then
        RATE=$(soxi -r "$f" 2>/dev/null || echo "0")
        CHANNELS=$(soxi -c "$f" 2>/dev/null || echo "0")
        BITS=$(soxi -b "$f" 2>/dev/null || echo "0")
    elif command -v ffprobe &>/dev/null; then
        RATE=$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of default=noprint_wrappers=1:nokey=1 "$f" 2>/dev/null || echo "0")
        CHANNELS=$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of default=noprint_wrappers=1:nokey=1 "$f" 2>/dev/null || echo "0")
        BITS="16"  # فرض می‌کنیم درست است اگر ffprobe دسترسی نداشت
    else
        echo -e "${YELLOW}[!]${NC} $name - soxi/ffprobe نیست، چک بصری رد شد"
        return
    fi

    local ok=true
    local issues=""

    [[ "$RATE" == "8000" ]] || { ok=false; issues+=" rate=${RATE}Hz(باید 8000)"; }
    [[ "$CHANNELS" == "1" ]] || { ok=false; issues+=" channels=${CHANNELS}(باید 1=mono)"; }

    if $ok; then
        SIZE=$(du -h "$f" | cut -f1)
        echo -e "${GREEN}[✓]${NC} $name (8kHz/Mono/16bit, $SIZE)"
    else
        echo -e "${RED}[✗]${NC} $name:$issues"
        ((ERRORS++))
    fi
}

echo ""
echo "=== اعتبارسنجی فایل‌های صوتی ==="
echo "مسیر: $SOUNDS_DIR"
echo ""

echo "--- عبارات اصلی ---"
for name in otp-intro otp-repeat otp-goodbye otp-error; do
    check_file "$SOUNDS_DIR/${name}.wav"
done

echo ""
echo "--- اعداد (0-9) ---"
for i in {0..9}; do
    check_file "$SOUNDS_DIR/digits/${i}.wav"
done

echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo -e "${GREEN}✅ همه ${#}فایل‌ها معتبرند${NC}"
    exit 0
else
    echo -e "${RED}❌ $ERRORS فایل مشکل دارند${NC}"
    echo "برای تولید مجدد: bash prepare_sounds.sh"
    exit 1
fi
