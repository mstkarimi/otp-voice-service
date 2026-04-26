import pytest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


VALID_API_KEY = "test-api-key-12345"
API_KEY_HASH = None


def _get_hash():
    from passlib.context import CryptContext
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return ctx.hash(VALID_API_KEY)


@pytest.fixture
def client():
    """TestClient با mock های لازم"""
    global API_KEY_HASH
    API_KEY_HASH = _get_hash()

    # mock config
    mock_config = MagicMock()
    mock_config.api.api_key_hash = API_KEY_HASH
    mock_config.api.ip_whitelist = []
    mock_config.asterisk.trunk = "90004455"
    mock_config.asterisk.caller_id = "90004455"
    mock_config.sounds.use_system_digits = False
    mock_config.logging.level = "WARNING"
    mock_config.logging.dir = "/tmp/otp-test"
    mock_config.logging.max_bytes = 1048576
    mock_config.logging.backup_count = 1
    mock_config.database.path = ":memory:"
    mock_config.rate_limit.per_number_calls = 3
    mock_config.rate_limit.per_number_window_minutes = 10
    mock_config.rate_limit.max_concurrent_calls = 20
    mock_config.rate_limit.hourly_limit = 500

    mock_ami = MagicMock()
    mock_ami.is_connected = True
    mock_ami.send_action = AsyncMock(return_value={"Response": "Success"})

    from src.core.rate_limiter import init_rate_limiter
    from src.ami.originator import init_originator

    rl = init_rate_limiter(3, 10, 20, 500)
    init_originator("90004455", "90004455", False)

    with patch("src.config.get_config", return_value=mock_config), \
         patch("src.ami.client.get_ami_client", return_value=mock_ami), \
         patch("src.core.rate_limiter.get_rate_limiter", return_value=rl), \
         patch("src.storage.db.create_call_record", new_callable=AsyncMock,
               return_value="test-uuid-1234"), \
         patch("src.storage.db.get_call_record", new_callable=AsyncMock,
               return_value={
                   "request_id": "test-uuid-1234",
                   "status": "completed",
                   "duration": 15,
                   "hangup_cause": "NORMAL_CLEARING"
               }):
        from fastapi.testclient import TestClient
        from src.api.routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        yield TestClient(app)


def auth_headers():
    return {"Authorization": f"Bearer {VALID_API_KEY}"}


def test_health_check(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["api"] == "ok"
    assert "active_calls" in data


def test_send_otp_valid(client):
    resp = client.post(
        "/api/v1/otp/call",
        json={"mobile": "09123456789", "code": "12345", "repeat": 2},
        headers=auth_headers(),
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "queued"
    assert "request_id" in data


def test_send_otp_invalid_mobile(client):
    resp = client.post(
        "/api/v1/otp/call",
        json={"mobile": "12345678901", "code": "12345"},
        headers=auth_headers(),
    )
    assert resp.status_code == 422


def test_send_otp_invalid_code(client):
    resp = client.post(
        "/api/v1/otp/call",
        json={"mobile": "09123456789", "code": "abc"},
        headers=auth_headers(),
    )
    assert resp.status_code == 422


def test_send_otp_no_auth(client):
    resp = client.post(
        "/api/v1/otp/call",
        json={"mobile": "09123456789", "code": "12345"},
    )
    assert resp.status_code == 401


def test_get_status(client):
    resp = client.get(
        "/api/v1/otp/status/test-uuid-1234",
        headers=auth_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
