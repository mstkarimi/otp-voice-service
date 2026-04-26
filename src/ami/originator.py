import asyncio
from typing import Optional, Tuple
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
        mobile: str,
        code: str,
        repeat: int = 2,
        timeout: int = 30,
    ) -> Tuple[bool, Optional[str]]:
        """
        شروع تماس صوتی OTP.
        Returns: (success, error_message)
        """
        mobile = sanitize_ami_value(mobile)
        code = sanitize_ami_value(code)
        repeat = max(1, min(3, int(repeat)))

        logger.info(
            f"Originating call to {mask_mobile(mobile)} "
            f"code={mask_code(code)} repeat={repeat}"
        )

        ami = get_ami_client()
        if not ami.is_connected:
            return False, "سرویس AMI در دسترس نیست"

        context = self._build_context()
        action = {
            "Action": "Originate",
            "Channel": f"SIP/{self._trunk}/{mobile}",
            "Context": context,
            "Exten": "s",
            "Priority": "1",
            "CallerID": self._caller_id,
            "Timeout": str(timeout * 1000),
            "Async": "true",
            "Variable": f"OTP_CODE={code},OTP_REPEAT={repeat}",
        }

        try:
            result = await asyncio.wait_for(
                ami.send_action(action),
                timeout=timeout + 5,
            )
            if result and result.get("Response") == "Success":
                logger.info(f"Call originated successfully to {mask_mobile(mobile)}")
                return True, None
            else:
                reason = result.get("Message", "خطای ناشناخته AMI") if result else "پاسخی از AMI دریافت نشد"
                logger.warning(f"Originate failed for {mask_mobile(mobile)}: {reason}")
                return False, reason
        except asyncio.TimeoutError:
            logger.error(f"Originate timeout for {mask_mobile(mobile)}")
            return False, "زمان انتظار برای پاسخ AMI تمام شد"
        except ConnectionError as e:
            logger.error(f"AMI connection error: {e}")
            return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error during originate: {e}")
            return False, "خطای داخلی سرور"


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
