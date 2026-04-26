# کانفیگ‌های Asterisk

## install.sh این کار را می‌کند

اسکریپت نصب به صورت خودکار این فایل‌ها را append می‌کند:

```bash
# مسیرهای هدف روی سرور Issabel
/etc/asterisk/extensions_custom.conf   ← dialplan اضافه می‌شه
/etc/asterisk/manager_custom.conf      ← AMI user اضافه می‌شه
```

## اگر نیاز به نصب دستی داشتید

### ۱. کپی کانفیگ AMI
```bash
# backup
cp /etc/asterisk/manager_custom.conf /etc/asterisk/manager_custom.conf.bak

# append
cat asterisk/manager_custom.conf >> /etc/asterisk/manager_custom.conf

# جایگزینی secret با یک رمز واقعی
sed -i 's/OTP_AMI_SECRET_PLACEHOLDER/YOUR_RANDOM_SECRET/' /etc/asterisk/manager_custom.conf
```

### ۲. کپی dialplan
```bash
# backup
cp /etc/asterisk/extensions_custom.conf /etc/asterisk/extensions_custom.conf.bak

# append
cat asterisk/extensions_custom.conf >> /etc/asterisk/extensions_custom.conf
```

### ۳. Reload (بدون restart)
```bash
asterisk -rx "dialplan reload"
asterisk -rx "manager reload"
```

### ۴. تست dialplan
```bash
asterisk -rx "dialplan show otp-playback-custom"
```

## نکته مهم

هرگز از `core restart` استفاده نکنید — فقط `dialplan reload` و `manager reload`.
