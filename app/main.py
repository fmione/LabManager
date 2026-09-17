import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models, realtime, settings as app_settings
from app.auth import hash_password
from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME
from app.database import SessionLocal, get_db, init_db
from app.mqtt import MQTT_STATUS, start_ingestor, stop_ingestor
from app.routers import (
    auth_routes,
    data_routes,
    experiments_routes,
    notes_routes,
    sensors_routes,
    settings_routes,
    units_routes,
    users_routes,
)
from app.web import render, require_roles

logging.basicConfig(level=logging.INFO)

LATEST_PER_SENSOR_SQL = text(
    """
    SELECT DISTINCT ON (sd.sensor_id)
           sd.sensor_id, sd.value, sd.time,
           s.name AS sensor_name, s.unit_id, s.data_type
    FROM sensor_data sd
    JOIN sensors s ON s.id = sd.sensor_id
    ORDER BY sd.sensor_id, sd.time DESC
    """
)


def seed_admin():
    db = SessionLocal()
    try:
        exists = db.query(models.User).filter_by(username=ADMIN_USERNAME).first()
        if not exists:
            db.add(
                models.User(
                    username=ADMIN_USERNAME,
                    email=ADMIN_EMAIL,
                    password_hash=hash_password(ADMIN_PASSWORD),
                    role="admin",
                )
            )
            db.commit()
            logging.info("Usuario admin por defecto creado: %s", ADMIN_USERNAME)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    realtime.set_loop(asyncio.get_running_loop())
    init_db()
    seed_admin()
    db = SessionLocal()
    try:
        app_settings.reload(db)
    finally:
        db.close()
    start_ingestor()
    yield
    stop_ingestor()


app = FastAPI(title="LabManager", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_routes.router)
app.include_router(users_routes.router)
app.include_router(experiments_routes.router)
app.include_router(sensors_routes.router)
app.include_router(units_routes.router)
app.include_router(data_routes.router)
app.include_router(notes_routes.router)
app.include_router(settings_routes.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    require_roles(request, {"admin", "investigador", "lector"})
    counts = {
        "experimentos": db.query(models.Experiment).count(),
        "sensores": db.query(models.Sensor).count(),
        "unidades": db.query(models.Unit).count(),
        "usuarios": db.query(models.User).count(),
    }
    last_read = (
        db.query(models.SensorData.time)
        .order_by(models.SensorData.time.desc())
        .first()
    )

    messages_24h = (
        db.query(models.SensorData)
        .filter(models.SensorData.time >= datetime.now(timezone.utc) - timedelta(hours=24))
        .count()
    )

    latest = db.execute(LATEST_PER_SENSOR_SQL).mappings().all()
    latest_enriched = []
    for row in latest:
        sensor = db.get(models.Sensor, row["sensor_id"])
        unit_symbol = (sensor.unit.symbol or sensor.unit.name) if sensor and sensor.unit else ""
        latest_enriched.append({
            "sensor_id": row["sensor_id"],
            "sensor_name": row["sensor_name"],
            "value": row["value"],
            "time": row["time"],
            "unit": unit_symbol,
            "data_type": row["data_type"],
        })

    sensors = db.query(models.Sensor).order_by(models.Sensor.name).all()
    sensor_options = [
        {
            "id": s.id,
            "label": f"{s.name} ({s.unit.symbol or s.unit.name})" if s.unit else s.name,
            "unit": s.unit.symbol or s.unit.name if s.unit else "",
        }
        for s in sensors
    ]

    return render(
        request,
        "dashboard.html",
        {
            "counts": counts,
            "last_read": last_read[0] if last_read else None,
            "latest": latest_enriched,
            "sensor_options": sensor_options,
            "mqtt": {**MQTT_STATUS, "messages_24h": messages_24h},
        },
    )
