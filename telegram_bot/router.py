"""HTTP endpoints: the Telegram webhook and Mini App admin sign-in."""
import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import config, handlers, webapp_auth

log = logging.getLogger('kartej.telegram')
router = APIRouter(prefix='/api/telegram', tags=['telegram'])


@router.post('/webhook', include_in_schema=False)
async def webhook(request: Request,
                  secret: Annotated[str | None, Header(alias='X-Telegram-Bot-Api-Secret-Token')] = None):
    expected = config.webhook_secret()
    if not config.enabled() or not expected or not hmac.compare_digest(secret or '', expected):
        raise HTTPException(403)
    try:
        update = await request.json()
        await run_in_threadpool(handlers.handle, update)
    except Exception:  # noqa: BLE001 - always acknowledge so Telegram doesn't retry a broken update forever.
        log.exception('Telegram update failed')
    return {'ok': True}


class MiniAppLogin(BaseModel):
    initData: str = Field(min_length=1, max_length=4096)


@router.post('/admin-session')
def admin_session(body: MiniAppLogin):
    """Sign admins into the dashboard inside Telegram, without a password."""
    user = webapp_auth.validate_init_data(body.initData)
    if not user or not config.is_admin(user['id']):
        raise HTTPException(403, 'Bu Telegram hisobi admin emas.')
    from backend import main
    return {'token': main.create_session()}
