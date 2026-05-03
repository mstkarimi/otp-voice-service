from typing import Optional, List, Any
from pydantic import BaseModel, validator, Field


class OTPCallRequest(BaseModel):
    mobile: str = Field(..., description="شماره موبایل ایرانی")
    code: str = Field(..., description="کد OTP (۴ تا ۸ رقم)")
    repeat: int = Field(2, ge=1, le=3, description="تعداد تکرار (۱ تا ۳)")
    caller_id: Optional[str] = Field(None, description="CallerID اختیاری - از config پیشفرض می‌گیره")

    @validator("mobile")
    def mobile_must_be_valid(cls, v: str) -> str:
        from src.core.validator import normalize_mobile
        valid, normalized = normalize_mobile(v)
        if not valid:
            raise ValueError("شماره موبایل معتبر نیست (فرمت صحیح: 09XXXXXXXXX)")
        return normalized

    @validator("code")
    def code_must_be_valid(cls, v: str) -> str:
        from src.core.validator import validate_code
        valid, msg = validate_code(str(v))
        if not valid:
            raise ValueError(msg)
        return str(v).strip()

    class Config:
        schema_extra = {
            "example": {
                "mobile": "09123456789",
                "code": "12345",
                "repeat": 2,
            }
        }


class OTPCallResponse(BaseModel):
    request_id: str
    status: str
    estimated_time: int = Field(description="زمان تخمینی پاسخ (ثانیه)")


class TimelineEvent(BaseModel):
    at: float = Field(description="Unix timestamp (seconds)")
    event: str
    detail: Optional[str] = None


class CallStatusResponse(BaseModel):
    request_id: str
    status: str
    mobile: Optional[str] = None
    duration: Optional[int] = None
    hangup_cause: Optional[str] = None
    asterisk_reason: Optional[str] = None

    is_terminal: bool = Field(description="True if status will not change further")
    is_answered: bool = Field(description="True if the user picked up at any point")
    can_retry: bool = Field(description="True if a retry call makes sense (no_answer/busy/failed/...)")
    retry_count: int = 0
    parent_request_id: Optional[str] = None

    created_at: Optional[float] = None
    updated_at: Optional[float] = None

    timeline: List[TimelineEvent] = Field(default_factory=list)


class RetryRequest(BaseModel):
    code: Optional[str] = Field(None, description="کد جدید (اختیاری) — اگر ندید، همان کد قبلی استفاده می‌شود")
    repeat: Optional[int] = Field(None, ge=1, le=3)


class HealthResponse(BaseModel):
    api: str
    ami: str
    active_calls: int
    available_channels: int


class ErrorResponse(BaseModel):
    detail: str
