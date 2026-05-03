import asyncio
from typing import Optional, Tuple, Any
from src.ami.client import get_ami_client
from src.core.validator import sanitize_ami_value
from src.core.logger import get_logger, mask_mobile, mask_code

logger = get_logger()


class CallOriginator:
    """منطق Originate تماس از طریق AMI"""

    def __init__(
        self,
        trunk: str,
        caller_id: str,
        use_system_digits: bool = False,
    ):
        self._trunk = sanitize_ami_value(trunk)
        self._caller_id = sanitize_ami_value(caller_id)
        self._use_system_digits = use_system_digits

    def _build_context(self) -> str:
        if self._use_system_digits:
            return "otp-playback"
        return "otp-playback-custom"

    async def originate(
        self,
        request_id: str,
        mobile: str,
        code: str,
        repeat: int = 2,
        timeout: int = 30,
    ) -> Tuple[bool, Optional[str]]:
        """
        Send the Originate action.

        With Async=true, panoramisk's send_action returns a LIST containing:
          [ack, OriginateResponse]
        We forward the OriginateResponse to the EventHandler so it gets
        processed exactly like a real event.

        Returns (action_accepted, error_message)
        """
        mobile = sanitize_ami_value(mobile)
        code = sanitize_ami_value(code)
        repeat = max(1, min(3, int(repeat)))

        logger.info(
            f"Originating call to {mask_mobile(mobile)} "
            f"code={mask_code(code)} repeat={repeat} req={request_id}"
        )

        ami = get_ami_client()
        if not ami.is_connected:
            return False, "سرویس AMI در دسترس نیست"

        context = self._build_context()
        action = {
            "Action": "Originate",
            "ActionID": f"otp-{request_id}",
            "Channel": f"SIP/{self._trunk}/{mobile}",
            "Context": context,
            "Exten": "s",
            "Priority": "1",
            "CallerID": self._caller_id,
            "Timeout": str(timeout * 1000),
            "Async": "true",
            "Variable": (
                f"OTP_CODE={code},OTP_REPEAT={repeat},"
                f"OTP_REQUEST_ID={request_id}"
            ),
        }

        try:
            result = await asyncio.wait_for(
                ami.send_action(action),
                # OriginateResponse may take up to (timeout + dialplan-runtime).
                # Allow a generous buffer.
                timeout=timeout + 90,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Originate ack timeout for {mask_mobile(mobile)} req={request_id}")
            return False, "زمان انتظار برای پاسخ AMI تمام شد"
        except ConnectionError as e:
            logger.error(f"AMI connection error: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error during originate: {e}")
            return False, "خطای داخلی سرور"

        # Normalize to list
        messages = result if isinstance(result, list) else [result] if result else []
        if not messages:
            return False, "پاسخی از AMI دریافت نشد"

        ack = messages[0]
        if not _msg_get(ack, "Response") == "Success":
            reason = _msg_get(ack, "Message") or "AMI ناموفق"
            logger.warning(f"Originate rejected for {mask_mobile(mobile)}: {reason}")
            return False, reason

        # Forward later messages (e.g. OriginateResponse) to EventHandler
        for msg in messages[1:]:
            event_name = _msg_get(msg, "Event")
            if event_name == "OriginateResponse":
                try:
                    from src.ami.event_handler import get_event_handler
                    h = get_event_handler()
                    if h is not None:
                        await h._on_originate_response(None, msg)
                except Exception as e:
                    logger.error(f"Failed forwarding OriginateResponse: {e}")

        return True, None


def _msg_get(msg: Any, key: str, default: Optional[str] = None) -> Optional[str]:
    """Safely read a value from a panoramisk Message or dict."""
    if msg is None:
        return default
    if hasattr(msg, "get"):
        return msg.get(key, default)
    return getattr(msg, key, default)


_originator: Optional[CallOriginator] = None


def get_originator() -> CallOriginator:
    global _originator
    if _originator is None:
        raise RuntimeError("CallOriginator not initialized")
    return _originator


def init_originator(
    trunk: str,
    caller_id: str,
    use_system_digits: bool = False,
) -> CallOriginator:
    global _originator
    _originator = CallOriginator(trunk, caller_id, use_system_digits)
    return _originator
