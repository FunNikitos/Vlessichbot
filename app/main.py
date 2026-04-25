"""FastAPI app + bot lifecycle (polling/webhook switch)."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app.bot.dispatcher import create_bot, create_dispatcher
from app.config import settings
from app.db.session import engine
from app.redis import close_redis
from app.tasks.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("vlessich")

bot = create_bot()
dp = create_dispatcher()
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    log.info("Starting up (mode=%s)", settings.run_mode)
    _scheduler = await start_scheduler(bot)
    if settings.run_mode == "webhook" and settings.webhook_url:
        url = f"{settings.webhook_url.rstrip('/')}/webhook"
        await bot.set_webhook(url, secret_token=settings.webhook_secret)
        log.info("Webhook set: %s", url)
    yield
    log.info("Shutting down")
    await stop_scheduler(_scheduler)
    if settings.run_mode == "webhook":
        await bot.delete_webhook()
    await bot.session.close()
    await engine.dispose()
    await close_redis()


app = FastAPI(lifespan=lifespan, title="vlessich-1")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    from aiogram.types import Update

    if settings.webhook_secret:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if token != settings.webhook_secret:
            return Response(status_code=403)
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return Response(status_code=200)


async def _run_polling() -> None:
    global _scheduler
    log.info("Polling mode")
    _scheduler = await start_scheduler(bot)
    try:
        await dp.start_polling(bot)
    finally:
        await stop_scheduler(_scheduler)
        await bot.session.close()
        await engine.dispose()
        await close_redis()


if __name__ == "__main__":
    if settings.run_mode == "polling":
        asyncio.run(_run_polling())
    else:
        import uvicorn

        uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
