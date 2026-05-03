import asyncio
import sys
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.config import init_config, get_config
from src.core.logger import init_logger, get_logger
from src.core.rate_limiter import init_rate_limiter
from src.ami.client import init_ami_client, get_ami_client
from src.ami.originator import init_originator
from src.ami.event_handler import init_event_handler
from src.storage import db
from src.api.routes import router


def create_app(config_path=None):
    # type: (str) -> FastAPI
    config = init_config(config_path or os.environ.get("OTP_CONFIG", "/etc/otp-service/config.yaml"))

    init_logger(
        log_dir=config.logging.dir,
        level=config.logging.level,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
    )
    logger = get_logger()
    logger.info("Starting OTP Voice Service")

    app = FastAPI(
        title="OTP Voice Call Service",
        description="سرویس ارسال کد تایید از طریق تماس صوتی",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )

    @app.on_event("startup")
    async def startup() -> None:
        cfg = get_config()

        # init database
        await db.init_db(cfg.database.path)

        # init rate limiter
        init_rate_limiter(
            per_number_calls=cfg.rate_limit.per_number_calls,
            per_number_window_minutes=cfg.rate_limit.per_number_window_minutes,
            max_concurrent=cfg.rate_limit.max_concurrent_calls,
            hourly_limit=cfg.rate_limit.hourly_limit,
        )

        # init AMI
        ami = init_ami_client(
            host=cfg.asterisk.host,
            port=cfg.asterisk.port,
            username=cfg.asterisk.username,
            secret=cfg.asterisk.secret,
            reconnect_delay=cfg.asterisk.reconnect_delay,
        )
        await ami.connect()

        # init AMI event handler (drives call status from Asterisk events)
        init_event_handler(ami)

        # init originator
        init_originator(
            trunk=cfg.asterisk.trunk,
            caller_id=cfg.asterisk.caller_id,
            use_system_digits=cfg.sounds.use_system_digits,
        )

        # cleanup scheduler
        asyncio.get_event_loop().create_task(_periodic_cleanup())

        logger.info("OTP Voice Service started successfully")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("Shutting down OTP Voice Service...")
        await get_ami_client().close()
        await db.close_db()

    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger = get_logger()
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(status_code=500, content={"detail": "خطای داخلی سرور"})

    app.include_router(router, prefix="/api/v1")

    return app


async def _periodic_cleanup() -> None:
    """پاک‌سازی دوره‌ای رکوردهای منقضی هر ۵ دقیقه"""
    from src.core.rate_limiter import get_rate_limiter
    while True:
        await asyncio.sleep(300)
        try:
            await db.cleanup_expired()
            await get_rate_limiter().cleanup()
        except Exception as e:
            get_logger().error(f"Cleanup error: {e}")


app = create_app()


if __name__ == "__main__":
    import uvicorn
    config = get_config()
    uvicorn.run(
        "src.main:app",
        host=config.api.host,
        port=config.api.port,
        log_level=config.logging.level.lower(),
        access_log=True,
    )
