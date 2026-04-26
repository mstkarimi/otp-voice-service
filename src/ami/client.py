import asyncio
import panoramisk
from typing import Optional, Callable
from src.core.logger import get_logger

logger = get_logger()


class AMIClient:
    """
    Wrapper روی panoramisk با reconnect خودکار.
    فقط روی 127.0.0.1 وصل می‌شه (بر اساس manager_custom.conf).
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        secret: str,
        reconnect_delay: int = 5,
    ):
        self._host = host
        self._port = port
        self._username = username
        self._secret = secret
        self._reconnect_delay = reconnect_delay

        self._manager: Optional[panoramisk.Manager] = None
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._event_handlers: dict = {}

    async def connect(self) -> None:
        await self._do_connect()

    async def _do_connect(self) -> None:
        try:
            self._manager = panoramisk.Manager(
                host=self._host,
                port=self._port,
                username=self._username,
                secret=self._secret,
                loop=asyncio.get_event_loop(),
                on_login=self._on_login,
                on_disconnect=self._on_disconnect,
            )
            await self._manager.connect()
            logger.info(f"AMI connected to {self._host}:{self._port}")
        except Exception as e:
            logger.error(f"AMI connection failed: {e}")
            self._connected = False
            await self._schedule_reconnect()

    def _on_login(self, manager: panoramisk.Manager) -> None:
        self._connected = True
        logger.info("AMI login successful")

    def _on_disconnect(self, manager: panoramisk.Manager, exc: Optional[Exception]) -> None:
        self._connected = False
        logger.warning(f"AMI disconnected: {exc}")
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self._schedule_reconnect())

    async def _schedule_reconnect(self) -> None:
        logger.info(f"Reconnecting to AMI in {self._reconnect_delay}s...")
        await asyncio.sleep(self._reconnect_delay)
        await self._do_connect()

    async def send_action(self, action: dict) -> Optional[dict]:
        if not self._connected or self._manager is None:
            raise ConnectionError("AMI not connected")
        try:
            result = await self._manager.send_action(action)
            return result
        except Exception as e:
            logger.error(f"AMI send_action failed: {e}")
            raise

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def close(self) -> None:
        if self._manager:
            try:
                self._manager.close()
            except Exception:
                pass
        self._connected = False
        logger.info("AMI connection closed")


_ami_client: Optional[AMIClient] = None


def get_ami_client() -> AMIClient:
    global _ami_client
    if _ami_client is None:
        raise RuntimeError("AMI client not initialized")
    return _ami_client


def init_ami_client(
    host: str,
    port: int,
    username: str,
    secret: str,
    reconnect_delay: int = 5,
) -> AMIClient:
    global _ami_client
    _ami_client = AMIClient(host, port, username, secret, reconnect_delay)
    return _ami_client
