from typing import Optional
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from src.config import get_config
from src.core.logger import get_logger

logger = get_logger()

_bearer = HTTPBearer(auto_error=False)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _extract_key(
    credentials: Optional[HTTPAuthorizationCredentials],
    request: Request,
) -> Optional[str]:
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.headers.get("X-API-Key")


def _verify_key(key: Optional[str]) -> bool:
    if not key:
        return False
    config = get_config()
    try:
        return _pwd_context.verify(key, config.api.api_key_hash)
    except Exception:
        return False


async def require_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer),
) -> str:
    key = _extract_key(credentials, request)
    if not _verify_key(key):
        logger.warning("Unauthorized API access attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key نامعتبر است",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return key


def hash_api_key(plain_key: str) -> str:
    return _pwd_context.hash(plain_key)
