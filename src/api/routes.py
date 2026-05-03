import asyncio
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Optional

from src.api.schemas import (
    OTPCallRequest,
    OTPCallResponse,
    CallStatusResponse,
    TimelineEvent,
    RetryRequest,
    HealthResponse,
)
from src.api.auth import require_api_key
from src.ami.client import get_ami_client
from src.ami.originator import get_originator
from src.core.rate_limiter import get_rate_limiter
from src.core.logger import get_logger, mask_mobile, mask_code
from src.storage import db

logger = get_logger()

router = APIRouter()


_ANSWERED_OR_LATER = {"answered", "playing", "completed"}


def _build_status_response(record: dict, events: list) -> CallStatusResponse:
    answered = (
        record["status"] in _ANSWERED_OR_LATER
        or any(ev["event"] in ("answered", "dialplan_start", "playing", "playback_complete")
               for ev in events)
    )
    is_terminal = record["status"] in db.TERMINAL_STATUSES
    can_retry = record["status"] in db.RETRYABLE_STATUSES
    return CallStatusResponse(
        request_id=record["request_id"],
        status=record["status"],
        mobile=record.get("mobile"),
        duration=record.get("duration"),
        hangup_cause=record.get("hangup_cause"),
        asterisk_reason=record.get("asterisk_reason"),
        is_terminal=is_terminal,
        is_answered=answered,
        can_retry=can_retry,
        retry_count=record.get("retry_count") or 0,
        parent_request_id=record.get("parent_request_id"),
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
        timeline=[TimelineEvent(**ev) for ev in events],
    )


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

    ok, msg = rate_limiter.check_concurrent_capacity()
    if not ok:
        raise HTTPException(status_code=503, detail=msg)

    ok, msg = await rate_limiter.check_hourly_limit()
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    ok, msg = await rate_limiter.check_number_limit(request.mobile)
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    code_masked = mask_code(request.code)
    request_id = await db.create_call_record(
        mobile=request.mobile,
        code=request.code,
        code_masked=code_masked,
    )

    background_tasks.add_task(
        _execute_call,
        request_id=request_id,
        mobile=request.mobile,
        code=request.code,
        repeat=request.repeat,
    )

    logger.info(
        f"OTP call queued: {mask_mobile(request.mobile)} "
        f"code={code_masked} request_id={request_id}"
    )

    return OTPCallResponse(
        request_id=request_id,
        status="queued",
        estimated_time=5,
    )


@router.post(
    "/otp/call/{request_id}/retry",
    response_model=OTPCallResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="تکرار تماس برای یک درخواست قبلی",
)
async def retry_call(
    request_id: str,
    body: RetryRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
) -> OTPCallResponse:
    record = await db.get_call_record(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="request_id یافت نشد")

    if record["status"] not in db.RETRYABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"این درخواست در وضعیت '{record['status']}' قابل retry نیست "
                   f"(فقط: {', '.join(sorted(db.RETRYABLE_STATUSES))})",
        )

    code = body.code or record.get("code")
    if not code:
        raise HTTPException(
            status_code=400,
            detail="کد اصلی موجود نیست (احتمالاً منقضی شده)؛ code جدید بدهید",
        )

    repeat = body.repeat if body.repeat else 2

    rate_limiter = get_rate_limiter()
    ok, msg = rate_limiter.check_concurrent_capacity()
    if not ok:
        raise HTTPException(status_code=503, detail=msg)
    ok, msg = await rate_limiter.check_hourly_limit()
    if not ok:
        raise HTTPException(status_code=429, detail=msg)
    ok, msg = await rate_limiter.check_number_limit(record["mobile"])
    if not ok:
        raise HTTPException(status_code=429, detail=msg)

    code_masked = mask_code(code)
    new_request_id = await db.create_call_record(
        mobile=record["mobile"],
        code=code,
        code_masked=code_masked,
        parent_request_id=request_id,
    )
    await db.increment_retry(request_id)

    background_tasks.add_task(
        _execute_call,
        request_id=new_request_id,
        mobile=record["mobile"],
        code=code,
        repeat=repeat,
    )

    logger.info(
        f"OTP retry queued: parent={request_id} new={new_request_id} "
        f"mobile={mask_mobile(record['mobile'])}"
    )

    return OTPCallResponse(
        request_id=new_request_id,
        status="queued",
        estimated_time=5,
    )


async def _execute_call(
    request_id: str,
    mobile: str,
    code: str,
    repeat: int,
) -> None:
    """
    Send the Originate to Asterisk. Final status is set asynchronously by
    the AMI EventHandler — we only mark the request as 'originating' or 'failed'
    based on the immediate Originate-action acknowledgment.
    """
    rate_limiter = get_rate_limiter()
    originator = get_originator()

    rate_limiter.acquire_slot()
    await db.update_call_status(request_id, "originating")
    await db.add_event(request_id, "originating", None)

    try:
        accepted, error = await originator.originate(
            request_id=request_id,
            mobile=mobile,
            code=code,
            repeat=repeat,
        )
        if not accepted:
            await db.update_call_status(request_id, "failed", hangup_cause=error)
            await db.add_event(request_id, "failed", f"originate not accepted: {error}")
            logger.warning(f"Originate not accepted [{request_id}]: {error}")

        # If accepted, do nothing here. The EventHandler will drive further status updates.

    except Exception as e:
        logger.error(f"Unexpected error in call execution [{request_id}]: {e}")
        await db.update_call_status(request_id, "failed", hangup_cause="INTERNAL_ERROR")
        await db.add_event(request_id, "failed", f"exception: {e}")
    finally:
        rate_limiter.release_slot()


@router.get(
    "/otp/status/{request_id}",
    response_model=CallStatusResponse,
    summary="وضعیت کامل تماس OTP (با timeline)",
)
async def get_call_status(
    request_id: str,
    _: str = Depends(require_api_key),
) -> CallStatusResponse:
    record = await db.get_call_record(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="request_id یافت نشد")
    events = await db.get_events(request_id)
    return _build_status_response(record, events)


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
