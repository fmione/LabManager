import os
from datetime import timezone
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from app import settings as app_settings

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)


def _local_tz() -> ZoneInfo:
    return app_settings.timezone()


def to_local(value):
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_local_tz())


def format_dt(value):
    dt = to_local(value)
    if dt is None:
        return "-"
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def format_dt_local(value):
    dt = to_local(value)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M")


templates.env.filters["dth"] = format_dt
templates.env.filters["dtlocal"] = format_dt_local
templates.env.filters["usym"] = lambda unit: (unit.symbol if unit and unit.symbol else unit.name) if unit else ""
