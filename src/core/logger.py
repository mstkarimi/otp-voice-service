import logging
import logging.handlers
import os
from typing import Optional


def setup_logger(
    name: str,
    log_dir: str,
    level: str = "INFO",
    max_bytes: int = 10485760,
    backup_count: int = 5,
) -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # فایل rotating
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "otp-service.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # stdout برای systemd journal
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    return logger


def mask_code(code: str) -> str:
    """نمایش masked کد OTP در لاگ: 12345 → 1***5"""
    if len(code) <= 2:
        return "*" * len(code)
    return code[0] + "*" * (len(code) - 2) + code[-1]


def mask_mobile(mobile: str) -> str:
    """نمایش masked موبایل: 09123456789 → 0912***6789"""
    if len(mobile) <= 7:
        return mobile
    return mobile[:4] + "***" + mobile[-4:]


_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        _logger = logging.getLogger("otp-service")
    return _logger


def init_logger(log_dir: str, level: str, max_bytes: int, backup_count: int) -> logging.Logger:
    global _logger
    _logger = setup_logger("otp-service", log_dir, level, max_bytes, backup_count)
    return _logger
