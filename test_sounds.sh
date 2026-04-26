#!/bin/bash
# =============================================================================
# پخش تست فایل‌های صوتی روی لپ‌تاپ
# اجرا: bash test_sounds.sh
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOUNDS_DIR="$SCRIPT_DIR/sounds"

command -v play &>/dev/null || command -v aplay &>/dev/null || {
    echo "play (sox) یا aplay نصب نیست"
    exit 1
}

PLAYER=""
command -v play  &>/dev/null && PLAYER="play -q"
command -v aplay &>/dev/null && PLAYER="${PLAYER:-aplay -q}"

play_file() {
    local f="$1"
    local label="$2"
    echo -n "  ▶ $label ... "
    if [[ -f "$f" ]]; then
        $PLAYER "$f" 2>/dev/null && echo "✓" || echo "خطا"
    else
        echo "فایل وجود ندارد: $f"
    fi
    sleep 0.3
}

echo ""
echo "=== تست پخش فایل‌های صوتی ==="
echo ""

echo "عبارات:"
play_file "$SOUNDS_DIR/otp-intro.wav"   "otp-intro (کد تایید شما)"
play_file "$SOUNDS_DIR/otp-repeat.wav"  "otp-repeat (تکرار می‌کنم...)"
play_file "$SOUNDS_DIR/otp-goodbye.wav" "otp-goodbye (با تشکر، خداحافظ)"
play_file "$SOUNDS_DIR/otp-error.wav"   "otp-error (خطایی رخ داد)"

echo ""
echo "اعداد:"
for i in {0..9}; do
    play_file "$SOUNDS_DIR/digits/${i}.wav" "digit $i"
done

echo ""
echo "=== تست کامل یک کد نمونه (1-2-3-4-5) ==="
sleep 0.5
play_file "$SOUNDS_DIR/otp-intro.wav"   "intro"
for d in 1 2 3 4 5; do
    play_file "$SOUNDS_DIR/digits/${d}.wav" "$d"
done
play_file "$SOUNDS_DIR/otp-goodbye.wav" "goodbye"

echo ""
echo "✅ تست پخش کامل شد"
