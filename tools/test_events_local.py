"""Standalone diagnostic: connect to AMI and watch which events fire for an Originate."""
import asyncio
import re
import sys

sys.path.insert(0, "/opt/otp-service")
import panoramisk

EVENTS_SEEN = []


async def main():
    cfg = open("/etc/otp-service/config.yaml").read()
    secret = re.search(r'secret:\s*"([^"]+)"', cfg).group(1)
    trunk = re.search(r'trunk:\s*"([^"]+)"', cfg).group(1)
    caller = re.search(r'caller_id:\s*"([^"]+)"', cfg).group(1)

    m = panoramisk.Manager(host="127.0.0.1", port=5038, username="otp_service", secret=secret)

    async def cb(manager, event):
        et = event.get("Event", "?")
        aid = event.get("ActionID", "")
        ch = event.get("Channel", "")
        EVENTS_SEEN.append((et, aid, ch, event.get("Response", ""), event.get("Reason", ""), event.get("Cause", "")))
        if "otp-" in str(aid) or "DEBUG-TEST" in str(ch):
            print("  EVENT:", et, "AID=", aid, "Ch=", ch, "Resp=", event.get("Response", ""), "Reason=", event.get("Reason", ""))

    m.register_event("*", cb)
    await m.connect()
    await asyncio.sleep(1)
    print("Connected. Sending Originate to invalid number...")

    action = {
        "Action": "Originate",
        "ActionID": "otp-DEBUG-TEST-001",
        "Channel": "SIP/" + trunk + "/09000000001",
        "Context": "otp-playback-custom",
        "Exten": "s", "Priority": "1",
        "CallerID": caller,
        "Timeout": "15000",
        "Async": "true",
        "Variable": "OTP_CODE=1234,OTP_REPEAT=2,OTP_REQUEST_ID=DEBUG-TEST-001",
    }
    res = await m.send_action(action)
    print("send_action returned: type=" + type(res).__name__ + " value=" + str(res)[:300])

    print("Waiting 25s for events...")
    await asyncio.sleep(25)

    print()
    print("Total events captured:", len(EVENTS_SEEN))
    otp_events = [e for e in EVENTS_SEEN if "otp-DEBUG" in str(e[1])]
    print("Events with our ActionID:", len(otp_events))
    for e in otp_events:
        print("  ", e)


if __name__ == "__main__":
    asyncio.run(main())
