import os
import yaml
from typing import List, Optional


class ApiConfig:
    def __init__(self, data: dict):
        self.host: str = data.get("host", "0.0.0.0")
        self.port: int = data.get("port", 8080)
        self.api_key_hash: str = data.get("api_key_hash", "")
        self.ip_whitelist: List[str] = data.get("ip_whitelist", [])


class AsteriskConfig:
    def __init__(self, data: dict):
        self.host: str = data.get("host", "127.0.0.1")
        self.port: int = data.get("port", 5038)
        self.username: str = data.get("username", "otp_service")
        self.secret: str = data.get("secret", "")
        self.trunk: str = data.get("trunk", "90004455")
        self.caller_id: str = data.get("caller_id", "CALLCENTER")
        self.call_timeout: int = data.get("call_timeout", 30)
        self.reconnect_delay: int = data.get("reconnect_delay", 5)


class RateLimitConfig:
    def __init__(self, data: dict):
        self.per_number_calls: int = data.get("per_number_calls", 3)
        self.per_number_window_minutes: int = data.get("per_number_window_minutes", 10)
        self.max_concurrent_calls: int = data.get("max_concurrent_calls", 20)
        self.hourly_limit: int = data.get("hourly_limit", 500)


class SoundsConfig:
    def __init__(self, data: dict):
        self.base_path: str = data.get("base_path", "/var/lib/asterisk/sounds/otp")
        self.use_system_digits: bool = data.get("use_system_digits", False)


class LoggingConfig:
    def __init__(self, data: dict):
        self.level: str = data.get("level", "INFO")
        self.dir: str = data.get("dir", "/var/log/otp-service")
        self.max_bytes: int = data.get("max_bytes", 10485760)
        self.backup_count: int = data.get("backup_count", 5)


class DatabaseConfig:
    def __init__(self, data: dict):
        self.path: str = data.get("path", "/var/lib/otp-service/otp.db")


class Config:
    def __init__(self, path: Optional[str] = None):
        config_path = path or os.environ.get("OTP_CONFIG", "/etc/otp-service/config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.api = ApiConfig(data.get("api", {}))
        self.asterisk = AsteriskConfig(data.get("asterisk", {}))
        self.rate_limit = RateLimitConfig(data.get("rate_limit", {}))
        self.sounds = SoundsConfig(data.get("sounds", {}))
        self.logging = LoggingConfig(data.get("logging", {}))
        self.database = DatabaseConfig(data.get("database", {}))


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config


def init_config(path: str) -> Config:
    global _config
    _config = Config(path)
    return _config
