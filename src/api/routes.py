import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Optional

from src.api.schemas import (
    OTPCallRequest,
    OTPCallResponse,
    CallStatusResponse,
    HealthResponse,
)
from src.api.auth import require_api_key
from src.ami.client import get_ami_client
from src.ami.originator import get_originator
from src.core.rate_limiter import get_rate_limiter
from src.core.logger import get_logger, mask_mobile, mask_code
from src.core.validator import sanitize_ami_value
from src.storage import db

logger = get_logger()

router = APIRouter()


@router.post(
    "/otp/call",
    response_model=OTPCallResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="ارسال کد OTP از طریق تماس صوتی",
)
async def send_otp_call(
    request: OTPCallRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
) -> OTPCallResponse:
    rate_limiter = get_rate_limiter()

    # چک ظرفیت همزمان
    ok, msg = rate_limiter.check_concurrent_capacity()
    if not ok:
        raise HTTPException(status_code=503, detail=msg)

    # چک hourly
    ok, msg = await rate_limiter.check_hourly_limit()
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    # چک per-number
    ok, msg = await rate_limiter.check_number_limit(request.mobile)
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    from src.core.logger import mask_code as _mask
    code_masked = _mask(request.code)
    request_id = await db.create_call_record(request.mobile, code_masked)

    background_tasks.add_task(
        _execute_call,
        request_id=request_id,
        mobile=request.mobile,
        code=request.code,
        repeat=request.repeat,
        caller_id=request.caller_id,
    )

    logger.info(
        f"OTP call queued: {mask_mobile(request.mobile)} "
        f"code={mask_code(request.code)} request_id={request_id}"
    )

    return OTPCallResponse(
        request_id=request_id,
        status="queued",
        estimated_time=5,
    )


async def _execute_call(
    request_id: str,
    mobile: str,
    code: str,
    repeat: int,
    caller_id: Optional[str],
) -> None:
    rate_limiter = get_rate_limiter()
    originator = get_originator()

    rate_limiter.acquire_slot()
    await db.update_call_status(request_id, "ringing")

    try:
        success, error = await originator.originate(
            mobile=mobile,
            code=code,
            repeat=repeat,
        )

        if success:
            await db.update_call_status(request_id, "completed", hangup_cause="NORMAL_CLEARING")
        else:
            await db.update_call_status(request_id, "failed", hangup_cause=error)
            logger.warning(f"Call failed [{request_id}]: {error}")

    except Exception as e:
        logger.error(f"Unexpected error in call execution [{request_id}]: {e}")
        await db.update_call_status(request_id, "failed", hangup_cause="INTERNAL_ERROR")
    finally:
        rate_limiter.release_slot()


@router.get(
    "/otp/status/{request_id}",
    response_model=CallStatusResponse,
    summary="وضعیت تماس OTP",
)
async def get_call_status(
    request_id: str,
    _: str = Depends(require_api_key),
) -> CallStatusResponse:
    record = await db.get_call_record(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="request_id یافت نشد")

    return CallStatusResponse(
        request_id=record["request_id"],
        status=record["status"],
        duration=record.get("duration"),
        hangup_cause=record.get("hangup_cause"),
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="وضعیت سلامت سرویس",
)
async def health_check() -> HealthResponse:
    ami = get_ami_client()
    rate_limiter = get_rate_limiter()

    return HealthResponse(
        api="ok",
        ami="connected" if ami.is_connected else "disconnected",
        active_calls=rate_limiter.active_calls,
        available_channels=rate_limiter.available_channels,
    )
