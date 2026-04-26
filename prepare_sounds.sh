#!/bin/bash
# =============================================================================
# آماده‌سازی فایل‌های صوتی فارسی (روی لپ‌تاپ با اینترنت)
# استراتژی: gTTS → espeak-ng
# اجرا: bash prepare_sounds.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOUNDS_DIR="$SCRIPT_DIR/sounds"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; }

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    آماده‌سازی فایل‌های صوتی فارسی        ║"
echo "╚══════════════════════════════════════════╝"

# بررسی sox
if ! command -v sox &>/dev/null; then
    error "sox نصب نیست."
    echo "  Ubuntu/Debian: sudo apt install sox"
    echo "  macOS:         brew install sox"
    exit 1
fi

# بررسی اینکه فایل‌ها از قبل موجودند
NEEDED_FILES=(
    "sounds/otp-intro.wav"
    "sounds/otp-repeat.wav"
    "sounds/otp-goodbye.wav"
    "sounds/otp-error.wav"
    "sounds/digits/0.wav"
    "sounds/digits/9.wav"
)
all_exist=true
for f in "${NEEDED_FILES[@]}"; do
    [[ -f "$SCRIPT_DIR/$f" ]] || { all_exist=false; break; }
done

if $all_exist; then
    log "فایل‌های صوتی از قبل موجودند"
    echo "برای تولید مجدد: rm -rf sounds/*.wav sounds/digits/ && bash prepare_sounds.sh"
    exit 0
fi

mkdir -p "$SOUNDS_DIR/digits"

# =============================================================================
# روش اول: gTTS (کیفیت بالا، نیاز به اینترنت)
# =============================================================================
try_gtts() {
    echo ""
    echo "[*] تلاش با gTTS..."

    if ! python3 -c "import gtts" 2>/dev/null; then
        warn "gTTS نصب نیست. نصب: pip3 install gtts"
        pip3 install gtts --quiet || return 1
    fi

    python3 "$SCRIPT_DIR/generate_sounds.py" "$SOUNDS_DIR" && return 0
    return 1
}

# =============================================================================
# روش دوم: espeak-ng (آفلاین، fallback)
# =============================================================================
try_espeak() {
    echo ""
    echo "[*] تلاش با espeak-ng (fallback)..."

    if ! command -v espeak-ng &>/dev/null; then
        warn "espeak-ng نصب نیست."
        if command -v apt &>/dev/null; then
            sudo apt install -y espeak-ng || return 1
        elif command -v brew &>/dev/null; then
            brew install espeak || return 1
        else
            error "espeak-ng را دستی نصب کنید"
            return 1
        fi
    fi

    declare -A WORDS=(
        [0]="صفر" [1]="یک" [2]="دو" [3]="سه" [4]="چهار"
        [5]="پنج" [6]="شش" [7]="هفت" [8]="هشت" [9]="نه"
    )

    for i in {0..9}; do
        tmp="$SOUNDS_DIR/digits/${i}_tmp.wav"
        dst="$SOUNDS_DIR/digits/${i}.wav"
        espeak-ng -v fa -s 130 "${WORDS[$i]}" -w "$tmp" 2>/dev/null
        sox "$tmp" -r 8000 -c 1 -b 16 -e signed-integer "$dst"
        rm "$tmp"
        echo "  [✓] digit $i"
    done

    declare -A PHRASES=(
        ["otp-intro"]="کد تایید شما"
        ["otp-repeat"]="تکرار می کنم کد تایید شما"
        ["otp-goodbye"]="با تشکر خداحافظ"
        ["otp-error"]="خطایی رخ داد"
    )

    for name in "${!PHRASES[@]}"; do
        tmp="$SOUNDS_DIR/${name}_tmp.wav"
        dst="$SOUNDS_DIR/${name}.wav"
        espeak-ng -v fa -s 130 "${PHRASES[$name]}" -w "$tmp" 2>/dev/null
        sox "$tmp" -r 8000 -c 1 -b 16 -e signed-integer "$dst"
        rm "$tmp"
        echo "  [✓] $name"
    done

    return 0
}

# =============================================================================
# اجرا با fallback
# =============================================================================
if try_gtts; then
    log "فایل‌ها با gTTS تولید شدند"
elif try_espeak; then
    warn "فایل‌ها با espeak-ng تولید شدند (کیفیت متوسط)"
else
    error "هیچ روش TTS در دسترس نبود"
    echo ""
    echo "راهنمای ضبط دستی:"
    echo "  ۱. هر عبارت زیر را با میکروفون ضبط کنید"
    echo "  ۲. با sox به فرمت Asterisk تبدیل کنید:"
    echo "     sox input.wav -r 8000 -c 1 -b 16 output.wav"
    echo ""
    echo "عبارات مورد نیاز:"
    echo "  sounds/otp-intro.wav   → 'کد تایید شما'"
    echo "  sounds/otp-repeat.wav  → 'تکرار می‌کنم، کد تایید شما'"
    echo "  sounds/otp-goodbye.wav → 'با تشکر، خداحافظ'"
    echo "  sounds/otp-error.wav   → 'خطایی رخ داد'"
    echo "  sounds/digits/0.wav    → 'صفر'"
    echo "  ... تا sounds/digits/9.wav"
    exit 1
fi

# اعتبارسنجی نهایی
echo ""
bash "$SCRIPT_DIR/validate_sounds.sh"
