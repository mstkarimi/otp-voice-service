import re
from typing import Tuple


# regex های تایید شماره موبایل ایرانی
_MOBILE_PATTERNS = [
    re.compile(r"^09\d{9}$"),           # 09123456789
    re.compile(r"^\+989\d{9}$"),        # +989123456789
    re.compile(r"^00989\d{9}$"),        # 00989123456789
    re.compile(r"^989\d{9}$"),          # 989123456789
]

_CODE_PATTERN = re.compile(r"^\d{4,8}$")

# کاراکترهای خطرناک برای AMI injection
_AMI_DANGEROUS = re.compile(r"[\r\n\x00]")


def normalize_mobile(mobile: str) -> Tuple[bool, str]:
    """
    نرمال‌سازی شماره موبایل به فرمت 09XXXXXXXXX
    Returns: (valid, normalized_number)
    """
    mobile = mobile.strip()

    # بلاک AMI injection
    if _AMI_DANGEROUS.search(mobile):
        return False, ""

    if re.match(r"^09\d{9}$", mobile):
        return True, mobile

    if re.match(r"^\+989\d{9}$", mobile):
        return True, "0" + mobile[3:]

    if re.match(r"^00989\d{9}$", mobile):
        return True, "0" + mobile[4:]

    if re.match(r"^989\d{9}$", mobile):
        return True, "0" + mobile[2:]

    return False, ""


def validate_code(code: str) -> Tuple[bool, str]:
    """
    اعتبارسنجی کد OTP
    Returns: (valid, error_message)
    """
    code = str(code).strip()

    if _AMI_DANGEROUS.search(code):
        return False, "کد حاوی کاراکتر غیرمجاز است"

    if not _CODE_PATTERN.match(code):
        return False, "کد باید بین ۴ تا ۸ رقم عددی باشد"

    return True, ""


def validate_repeat(repeat: int) -> Tuple[bool, str]:
    if not isinstance(repeat, int) or repeat < 1 or repeat > 3:
        return False, "تعداد تکرار باید بین ۱ تا ۳ باشد"
    return True, ""


def sanitize_ami_value(value: str) -> str:
    """حذف کاراکترهای خطرناک AMI از مقادیر"""
    return _AMI_DANGEROUS.sub("", str(value))
