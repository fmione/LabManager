from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app import settings as app_settings
from app.auth import ROLE_ADMIN
from app.database import get_db
from app.mqtt import restart_ingestor
from app.web import TIMEZONE_CHOICES, redirect, render, require_roles

router = APIRouter()


@router.get("/configuracion")
def settings_page(request: Request, db: Session = Depends(get_db)):
    require_roles(request, ROLE_ADMIN)
    return render(
        request,
        "settings.html",
        {
            "tz_choices": TIMEZONE_CHOICES,
            "current_tz": app_settings.timezone_name(),
            "mqtt_host": app_settings.mqtt_host(db),
            "mqtt_port": app_settings.mqtt_port(db),
        },
    )


@router.post("/configuracion")
def save_settings(
    request: Request,
    timezone: str = Form(...),
    mqtt_host: str = Form(...),
    mqtt_port: str = Form(...),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_ADMIN)
    app_settings.set(db, "timezone", timezone)
    app_settings.set(db, "mqtt_host", mqtt_host.strip())
    app_settings.set(db, "mqtt_port", mqtt_port.strip())
    restart_ingestor()
    return redirect("/configuracion", msg="Configuración guardada correctamente.")
