from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from app import settings as app_settings
from app.auth import ROLE_LABELS, read_session_token
from app.templating import templates

SESSION_COOKIE = "lm_session"

def _utc_tz_choices():
    choices = []
    for offset in range(-12, 15):
        value = f"Etc/GMT{-offset:+d}"
        if offset == -3:
            label = "UTC-3 (Argentina)"
        elif offset == 0:
            label = "UTC 0"
        else:
            label = f"UTC{offset:+d}"
        choices.append((label, value))
    return choices


TIMEZONE_CHOICES = _utc_tz_choices()


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return read_session_token(token)


def require_roles(request: Request, roles: set[str]) -> dict:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    if user["role"] not in roles:
        raise HTTPException(
            status_code=303,
            headers={"Location": redirect_url("/", error="No tenés permisos para esta acción.")},
        )
    return user


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    user = current_user(request)
    ctx = {
        "request": request,
        "user": user,
        "now": datetime.now(timezone.utc),
        "tz_name": app_settings.timezone_name(),
    }
    if user:
        ctx["role_label"] = ROLE_LABELS.get(user["role"], user["role"])
    if context:
        ctx.update(context)
    return templates.TemplateResponse(request, name, ctx, status_code=status_code)


def redirect_url(url: str, msg: str | None = None, error: str | None = None) -> str:
    params = {}
    if msg:
        params["msg"] = msg
    if error:
        params["error"] = error
    if params:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urlencode(params)}"
    return url


def redirect(url: str, msg: str | None = None, error: str | None = None) -> RedirectResponse:
    return RedirectResponse(redirect_url(url, msg, error), status_code=303)
