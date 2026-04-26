# فایل‌های صوتی OTP

## روش تولید

فایل‌ها با `bash prepare_sounds.sh` تولید می‌شوند.

| فایل | متن | روش تولید |
|------|-----|-----------|
| `otp-intro.wav` | کد تایید شما | gTTS / espeak-ng |
| `otp-repeat.wav` | تکرار می‌کنم، کد تایید شما | gTTS / espeak-ng |
| `otp-goodbye.wav` | با تشکر، خداحافظ | gTTS / espeak-ng |
| `otp-error.wav` | خطایی رخ داد | gTTS / espeak-ng |
| `digits/0.wav` | صفر | gTTS / espeak-ng |
| `digits/1.wav` | یک | gTTS / espeak-ng |
| `digits/2.wav` | دو | gTTS / espeak-ng |
| `digits/3.wav` | سه | gTTS / espeak-ng |
| `digits/4.wav` | چهار | gTTS / espeak-ng |
| `digits/5.wav` | پنج | gTTS / espeak-ng |
| `digits/6.wav` | شش | gTTS / espeak-ng |
| `digits/7.wav` | هفت | gTTS / espeak-ng |
| `digits/8.wav` | هشت | gTTS / espeak-ng |
| `digits/9.wav` | نه | gTTS / espeak-ng |

## مشخصات فنی (الزامات Asterisk)

- **فرمت:** WAV (PCM)
- **Sample Rate:** 8000 Hz
- **Channels:** Mono (1)
- **Bit Depth:** 16-bit signed integer

## اعتبارسنجی

```bash
bash validate_sounds.sh
```

## ضبط دستی

اگر می‌خواهید فایل‌ها را با صدای واقعی ضبط کنید:

```bash
# تبدیل هر فایل ضبط‌شده به فرمت Asterisk
sox input.wav -r 8000 -c 1 -b 16 -e signed-integer output.wav
```
