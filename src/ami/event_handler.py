"""
AMI event listener that updates call status in DB based on Asterisk events.

Wires up handlers for:
  - OriginateResponse  : final result of an Originate (matched by ActionID)
  - Newchannel         : channel created
  - Newstate           : channel state change (Ringing, Up)
  - Hangup             : channel hung up (with cause code)
  - UserEvent          : custom events fired from dialplan (OTPAnswered, OTPPlaybackStart/Complete)

A request is identified by:
  - ActionID = "otp-<request_id>" on Originate (we set this)
  - Channel variable OTP_REQUEST_ID (we set this; dialplan echoes it in UserEvents)
  - Channel name (mapped via the first OTPCallStart UserEvent)
"""
import time
from typing import Optional

from src.core.logger import get_logger
from src.storage import db

logger = get_logger()

ACTION_ID_PREFIX = "otp-"


# Hangup cause -> our status mapping. ITU-T Q.850 codes.
_CAUSE_TO_STATUS = {
    16: "completed",      # Normal call clearing
    17: "busy",           # User busy
    18: "no_answer",      # No user response
    19: "no_answer",      # No answer (user alerted)
    20: "no_answer",      # Subscriber absent
    21: "rejected",       # Call rejected
    22: "unreachable",    # Number changed
    27: "unreachable",    # Destination out of order
    28: "failed",         # Invalid number format
    34: "congestion",     # Circuit/channel congestion
    38: "congestion",     # Network out of order
    41: "congestion",     # Temporary failure
    42: "congestion",     # Switching equipment congestion
    50: "failed",         # Requested facility not subscribed
}

# OriginateResponse Reason -> status. Asterisk numeric codes.
_REASON_TO_STATUS = {
    "0": "failed",        # Hangup before any state
    "1": "no_answer",
    "2": "failed",
    "3": "failed",
    "4": "answered",      # Answered (call connected)
    "5": "busy",
    "8": "congestion",
}


def _extract_request_id(action_id: Optional[str]) -> Optional[str]:
    if not action_id:
        return None
    if action_id.startswith(ACTION_ID_PREFIX):
        return action_id[len(ACTION_ID_PREFIX):]
    return None


class EventHandler:
    """Registers AMI event callbacks that drive the call status machine."""

    def __init__(self, manager):
        self._manager = manager

    def register(self) -> None:
        m = self._manager
        if not m:
            logger.error("EventHandler: no manager to register on")
            return

        m.register_event("OriginateResponse", self._on_originate_response)
        m.register_event("Newchannel",        self._on_new_channel)
        m.register_event("Newstate",          self._on_new_state)
        m.register_event("Hangup",            self._on_hangup)
        m.register_event("UserEvent",         self._on_user_event)
        logger.info("AMI event handlers registered")

    # ---- handlers ----

    async def _on_originate_response(self, manager, message):
        request_id = _extract_request_id(message.get("ActionID"))
        if not request_id:
            return
        response = message.get("Response", "")
        reason   = str(message.get("Reason", ""))
        channel  = message.get("Channel")
        await db.add_event(
            request_id, "originate_response",
            f"response={response} reason={reason} channel={channel}",
        )
        if response == "Failure" or reason in ("0", "1", "5", "8"):
            new_status = _REASON_TO_STATUS.get(reason, "failed")
            await db.update_call_status(
                request_id,
                new_status,
                asterisk_reason=f"{reason}",
            )

    async def _on_new_channel(self, manager, message):
        # We don't have a request_id here unless the dialplan tells us via UserEvent;
        # OriginateResponse + Hangup carry the channel for matching.
        pass

    async def _on_new_state(self, manager, message):
        channel = message.get("Channel")
        if not channel:
            return
        record = await db.get_call_by_channel(channel)
        if not record:
            return
        request_id = record["request_id"]
        state_desc = message.get("ChannelStateDesc", "").lower()

        if state_desc == "ringing":
            await db.update_call_status(request_id, "ringing")
            await db.add_event(request_id, "ringing", f"channel={channel}")
        elif state_desc == "up":
            await db.update_call_status(request_id, "answered")
            await db.add_event(request_id, "answered", f"channel={channel}")

    async def _on_hangup(self, manager, message):
        channel = message.get("Channel")
        if not channel:
            return
        record = await db.get_call_by_channel(channel)
        if not record:
            return
        request_id = record["request_id"]

        cause_raw = message.get("Cause") or "0"
        try:
            cause_int = int(cause_raw)
        except (ValueError, TypeError):
            cause_int = 0
        cause_txt = (
            message.get("Cause-txt") or message.get("CauseTxt") or ""
        )

        await db.add_event(
            request_id, "hangup",
            f"cause={cause_int} ({cause_txt}) channel={channel}",
        )

        # If call was already in a terminal state, do nothing more.
        if record["status"] in db.TERMINAL_STATUSES:
            return

        # If the channel had been answered and dialplan completed playback,
        # the prior UserEvent may already have set 'completed'. In that case,
        # the next get_call_record(...) inside update_call_status will refuse
        # the override. So we just attempt our best mapping here.
        new_status = _CAUSE_TO_STATUS.get(cause_int)
        if new_status is None:
            # Fallback based on whether the call was ever answered
            new_status = "completed" if record["status"] in ("answered", "playing") else "failed"

        await db.update_call_status(
            request_id, new_status,
            hangup_cause=f"{cause_int} {cause_txt}".strip(),
        )

    async def _on_user_event(self, manager, message):
        ev = message.get("UserEvent") or message.get("Userevent")
        request_id = message.get("RequestID") or message.get("Requestid")
        if not request_id:
            return
        channel = message.get("Channel")

        if ev == "OTPCallStart":
            # Initial ping from dialplan — use it to bind channel ↔ request_id
            if channel:
                await db.update_call_status(request_id, "answered", channel=channel)
            await db.add_event(request_id, "dialplan_start", f"channel={channel}")
        elif ev == "OTPPlaybackStart":
            await db.update_call_status(request_id, "playing")
            await db.add_event(request_id, "playing", None)
        elif ev == "OTPPlaybackComplete":
            await db.update_call_status(request_id, "completed")
            await db.add_event(request_id, "playback_complete", None)


_handler: Optional[EventHandler] = None


def init_event_handler(ami_client) -> Optional[EventHandler]:
    """Create and register an EventHandler on top of the connected AMI client."""
    global _handler
    if ami_client._manager is None:
        logger.warning("init_event_handler: AMI manager not yet connected")
        return None
    _handler = EventHandler(ami_client._manager)
    _handler.register()
    return _handler


def get_event_handler() -> Optional[EventHandler]:
    return _handler
