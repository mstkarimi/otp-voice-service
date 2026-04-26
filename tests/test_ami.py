import pytest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ami.originator import CallOriginator


@pytest.fixture
def originator():
    return CallOriginator(trunk="90004455", caller_id="90004455", use_system_digits=False)


@pytest.mark.asyncio
async def test_originate_success(originator):
    mock_ami = MagicMock()
    mock_ami.is_connected = True
    mock_ami.send_action = AsyncMock(return_value={"Response": "Success"})

    with patch("src.ami.originator.get_ami_client", return_value=mock_ami):
        success, error = await originator.originate("09120000001", "12345", repeat=2)

    assert success
    assert error is None

    # بررسی action ارسالی
    call_args = mock_ami.send_action.call_args[0][0]
    assert call_args["Action"] == "Originate"
    assert "SIP/90004455/09120000001" in call_args["Channel"]
    assert "OTP_CODE=12345" in call_args["Variable"]
    assert "OTP_REPEAT=2" in call_args["Variable"]


@pytest.mark.asyncio
async def test_originate_ami_failure(originator):
    mock_ami = MagicMock()
    mock_ami.is_connected = True
    mock_ami.send_action = AsyncMock(return_value={"Response": "Error", "Message": "Channel unavailable"})

    with patch("src.ami.originator.get_ami_client", return_value=mock_ami):
        success, error = await originator.originate("09120000001", "12345")

    assert not success
    assert "Channel unavailable" in error


@pytest.mark.asyncio
async def test_originate_not_connected(originator):
    mock_ami = MagicMock()
    mock_ami.is_connected = False

    with patch("src.ami.originator.get_ami_client", return_value=mock_ami):
        success, error = await originator.originate("09120000001", "12345")

    assert not success
    assert "AMI" in error


@pytest.mark.asyncio
async def test_originate_sanitizes_input(originator):
    mock_ami = MagicMock()
    mock_ami.is_connected = True
    mock_ami.send_action = AsyncMock(return_value={"Response": "Success"})

    with patch("src.ami.originator.get_ami_client", return_value=mock_ami):
        await originator.originate("09120000001\r\n", "1234\r\n")

    call_args = mock_ami.send_action.call_args[0][0]
    assert "\r" not in call_args["Variable"]
    assert "\n" not in call_args["Variable"]


@pytest.mark.asyncio
async def test_originate_repeat_clamped(originator):
    mock_ami = MagicMock()
    mock_ami.is_connected = True
    mock_ami.send_action = AsyncMock(return_value={"Response": "Success"})

    with patch("src.ami.originator.get_ami_client", return_value=mock_ami):
        await originator.originate("09120000001", "12345", repeat=99)

    call_args = mock_ami.send_action.call_args[0][0]
    assert "OTP_REPEAT=3" in call_args["Variable"]


@pytest.mark.asyncio
async def test_uses_custom_context(originator):
    mock_ami = MagicMock()
    mock_ami.is_connected = True
    mock_ami.send_action = AsyncMock(return_value={"Response": "Success"})

    with patch("src.ami.originator.get_ami_client", return_value=mock_ami):
        await originator.originate("09120000001", "12345")

    call_args = mock_ami.send_action.call_args[0][0]
    assert call_args["Context"] == "otp-playback-custom"


@pytest.mark.asyncio
async def test_uses_system_context():
    orig = CallOriginator(trunk="90004455", caller_id="90004455", use_system_digits=True)
    mock_ami = MagicMock()
    mock_ami.is_connected = True
    mock_ami.send_action = AsyncMock(return_value={"Response": "Success"})

    with patch("src.ami.originator.get_ami_client", return_value=mock_ami):
        await orig.originate("09120000001", "12345")

    call_args = mock_ami.send_action.call_args[0][0]
    assert call_args["Context"] == "otp-playback"
