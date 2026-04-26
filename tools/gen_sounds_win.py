#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Persian OTP sounds with gTTS + ffmpeg on Windows"""

import os
import sys
import subprocess
import io

# Fix Windows console encoding
if sys.platform == "win32":
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")

PERSIAN_NUMBERS = {
    0: "صفر", 1: "یک", 2: "دو", 3: "سه", 4: "چهار",
    5: "پنج", 6: "شش", 7: "هفت", 8: "هشت", 9: "نه",
}

PHRASES = {
    "otp-intro":   "کد تایید شما",
    "otp-repeat":  "تکرار می‌کنم، کد تایید شما",
    "otp-goodbye": "با تشکر، خداحافظ",
    "otp-error":   "خطایی رخ داد، لطفاً دوباره تلاش کنید",
}

def mp3_to_wav_asterisk(mp3_data: bytes, out_path: str) -> None:
    """تبدیل MP3 bytes به WAV 8kHz Mono 16-bit با ffmpeg"""
    cmd = [
        FFMPEG, "-y",
        "-i", "pipe:0",
        "-ar", "8000",
        "-ac", "1",
        "-acodec", "pcm_s16le",
        out_path,
    ]
    proc = subprocess.run(
        cmd,
        input=mp3_data,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode()}")


def generate(output_dir: str) -> None:
    try:
        from gtts import gTTS
    except ImportError:
        print("gTTS نصب نیست: pip install gtts")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "digits"), exist_ok=True)

    print("\n[*] تولید اعداد فارسی (0-9)...")
    for num, word in PERSIAN_NUMBERS.items():
        dst = os.path.join(output_dir, "digits", f"{num}.wav")
        print(f"  {num} → '{word}' ", end="", flush=True)
        buf = io.BytesIO()
        gTTS(text=word, lang="fa", slow=False).write_to_fp(buf)
        mp3_to_wav_asterisk(buf.getvalue(), dst)
        print("✓")

    print("\n[*] تولید عبارات OTP...")
    for name, text in PHRASES.items():
        dst = os.path.join(output_dir, f"{name}.wav")
        print(f"  {name}: '{text}' ", end="", flush=True)
        buf = io.BytesIO()
        gTTS(text=text, lang="fa", slow=False).write_to_fp(buf)
        mp3_to_wav_asterisk(buf.getvalue(), dst)
        print("✓")

    print(f"\n[✓] همه صداها در: {output_dir}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds"
    )
    generate(out)
