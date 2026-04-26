#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Persian OTP sound files using Microsoft Edge TTS + ffmpeg
Voice: fa-IR-DilaraNeural (female) or fa-IR-FaridNeural (male)
"""

import os
import sys
import asyncio
import subprocess
import tempfile

FFMPEG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
VOICE  = "fa-IR-DilaraNeural"   # صدای زنانه فارسی Microsoft

PERSIAN_NUMBERS = {
    0: "صفر", 1: "یک", 2: "دو", 3: "سه", 4: "چهار",
    5: "پنج", 6: "شش", 7: "هفت", 8: "هشت", 9: "نه",
}

PHRASES = {
    "otp-intro":   "کد تایید شما",
    "otp-repeat":  "تکرار می کنم، کد تایید شما",
    "otp-goodbye": "با تشکر، خداحافظ",
    "otp-error":   "خطایی رخ داد، لطفا دوباره تلاش کنید",
}


async def tts_to_mp3(text: str, out_mp3: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(out_mp3)


def mp3_to_asterisk_wav(mp3_path: str, wav_path: str) -> None:
    """Convert MP3 to WAV: 8kHz, Mono, 16-bit PCM"""
    cmd = [
        FFMPEG, "-y", "-i", mp3_path,
        "-ar", "8000", "-ac", "1",
        "-acodec", "pcm_s16le",
        wav_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr.decode()}")


async def generate_all(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "digits"), exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        print("[*] Generating Persian digits (0-9)...")
        for num, word in PERSIAN_NUMBERS.items():
            tmp_mp3 = os.path.join(tmpdir, f"{num}.mp3")
            dst_wav = os.path.join(output_dir, "digits", f"{num}.wav")
            sys.stdout.write(f"  digit {num} ({word})... ")
            sys.stdout.flush()
            await tts_to_mp3(word, tmp_mp3)
            mp3_to_asterisk_wav(tmp_mp3, dst_wav)
            print("OK")

        print("\n[*] Generating OTP phrases...")
        for name, text in PHRASES.items():
            tmp_mp3 = os.path.join(tmpdir, f"{name}.mp3")
            dst_wav = os.path.join(output_dir, f"{name}.wav")
            sys.stdout.write(f"  {name}... ")
            sys.stdout.flush()
            await tts_to_mp3(text, tmp_mp3)
            mp3_to_asterisk_wav(tmp_mp3, dst_wav)
            print("OK")

    print(f"\n[OK] All sound files generated in: {output_dir}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sounds"
    )
    asyncio.run(generate_all(out))
