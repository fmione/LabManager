"""Lectura/escritura de configuración de la app desde la tabla `settings`.

Al ser una app de laboratorio mono-instancia, mantenemos una caché en
proceso (`_CACHE`) consultada por plantillas/filtros/JS sin tocar la DB en
cada render. La caché se invalida al guardar desde el panel de configuración
y se recarga en el arranque.
"""

import logging

from zoneinfo import ZoneInfo

from app.config import MQTT_HOST, MQTT_PORT
from app.models import Setting

logger = logging.getLogger("labmanager.settings")

DEFAULT_TZ = "Etc/GMT+3"

_CACHE: dict[str, str] = {}

_REQUIRED = {
    "timezone": DEFAULT_TZ,
    "mqtt_host": MQTT_HOST,
    "mqtt_port": str(MQTT_PORT),
}


def get(db, key: str, default: str | None = None) -> str | None:
    """Devuelve el valor crudo de una setting (sin recargar la caché)."""
    if not _CACHE and default is None:
        reload(db)
    return _CACHE.get(key, default)


def reload(db) -> None:
    """Recarga la caché desde la DB (llamar en arranque y tras guardar)."""
    global _CACHE
    _CACHE = {}
    try:
        rows = db.query(Setting).all()
        for row in rows:
            _CACHE[row.key] = row.value
    except Exception:
        logger.debug("settings aún no disponibles; usando defaults.", exc_info=True)
        _CACHE = {}
    for k, v in _REQUIRED.items():
        _CACHE.setdefault(k, v)


def set(db, key: str, value: str) -> None:
    """Guarda una setting y actualiza la caché en memoria."""
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()
    _CACHE[key] = value


def timezone_name(db=None) -> str:
    """Nombre IANA de la zona horaria configurada."""
    if db is None:
        return _CACHE.get("timezone", DEFAULT_TZ)
    return get(db, "timezone", DEFAULT_TZ) or DEFAULT_TZ


def timezone(db=None) -> ZoneInfo:
    return ZoneInfo(timezone_name(db))


def mqtt_host(db=None) -> str:
    return get(db, "mqtt_host", MQTT_HOST) or MQTT_HOST


def mqtt_port(db=None) -> int:
    try:
        return int(get(db, "mqtt_port", str(MQTT_PORT)) or MQTT_PORT)
    except (TypeError, ValueError):
        return MQTT_PORT
