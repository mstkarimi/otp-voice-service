#!/usr/bin/env python3
"""
تولید فایل‌های صوتی فارسی با gTTS + تبدیل با sox به فرمت Asterisk
اجرا: python3 generate_sounds.py
"""

import os
import subprocess
import sys


PERSIAN_NUMBERS = {
    0: "صفر",
    1: "یک",
    2: "دو",
    3: "سه",
    4: "چهار",
    5: "پنج",
    6: "شش",
    7: "هفت",
    8: "هشت",
    9: "نه",
}

PHRASES = {
    "otp-intro":   "کد تایید شما",
    "otp-repeat":  "تکرار می‌کنم، کد تایید شما",
    "otp-goodbye": "با تشکر، خداحافظ",
    "otp-error":   "خطایی رخ داد، لطفاً دوباره تلاش کنید",
}


def check_dependencies():
    try:
        import gtts
        print("[✓] gTTS موجود است")
    except ImportError:
        print("[✗] gTTS نصب نیست. نصب: pip3 install gtts")
        sys.exit(1)

    try:
        subprocess.run(["sox", "--version"], capture_output=True, check=True)
        print("[✓] sox موجود است")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[✗] sox نصب نیست.")
        print("  Linux: sudo apt install sox / sudo yum install sox")
        print("  macOS: brew install sox")
        sys.exit(1)


def to_asterisk_wav(src_mp3: str, dst_wav: str) -> None:
    """تبدیل mp3 به WAV با مشخصات Asterisk: 8kHz, Mono, 16-bit PCM"""
    subprocess.run([
        "sox", src_mp3,
        "-r", "8000",
        "-c", "1",
        "-b", "16",
        "-e", "signed-integer",
        dst_wav
    ], check=True, capture_output=True)


def generate(output_dir: str = "sounds") -> None:
    from gtts import gTTS

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "digits"), exist_ok=True)

    # تولید اعداد
    print("\n[*] تولید اعداد فارسی (0-9)...")
    for num, word in PERSIAN_NUMBERS.items():
        tmp_mp3 = os.path.join(output_dir, "digits", f"{num}_tmp.mp3")
        dst_wav = os.path.join(output_dir, "digits", f"{num}.wav")

        print(f"  {num} → '{word}'", end=" ", flush=True)
        tts = gTTS(text=word, lang="fa", slow=False)
        tts.save(tmp_mp3)
        to_asterisk_wav(tmp_mp3, dst_wav)
        os.remove(tmp_mp3)
        print("✓")

    # تولید عبارات
    print("\n[*] تولید عبارات فارسی...")
    for name, text in PHRASES.items():
        tmp_mp3 = os.path.join(output_dir, f"{name}_tmp.mp3")
        dst_wav = os.path.join(output_dir, f"{name}.wav")

        print(f"  {name} → '{text}'", end=" ", flush=True)
        tts = gTTS(text=text, lang="fa", slow=False)
        tts.save(tmp_mp3)
        to_asterisk_wav(tmp_mp3, dst_wav)
        os.remove(tmp_mp3)
        print("✓")

    print("\n[✓] همه فایل‌های صوتی تولید شدند در:", output_dir)
    print("    حالا validate_sounds.sh را اجرا کنید.")


if __name__ == "__main__":
    check_dependencies()
    out = sys.argv[1] if len(sys.argv) > 1 else "sounds"
    generate(out)
