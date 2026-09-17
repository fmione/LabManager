import re

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app import models
from app.auth import ROLE_WRITE
from app.database import get_db
from app.web import redirect, render, require_roles

router = APIRouter()

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{2,80}$")
TYPES = ("float", "bool")


@router.get("/sensores")
def sensors_page(request: Request, db: Session = Depends(get_db)):
    require_roles(request, {"admin", "investigador", "lector"})
    sensors = db.query(models.Sensor).order_by(models.Sensor.name).all()
    units = db.query(models.Unit).order_by(models.Unit.name).all()
    return render(request, "sensors.html", {"sensores": sensors, "unidades": units})


@router.get("/sensores/{sensor_id}")
def sensor_detail(
    sensor_id: int, request: Request, db: Session = Depends(get_db)
):
    require_roles(request, {"admin", "investigador", "lector"})
    sensor = db.get(models.Sensor, sensor_id)
    if sensor is None:
        return redirect("/sensores", error="Sensor no encontrado.")
    units = db.query(models.Unit).order_by(models.Unit.name).all()
    experimentos = sorted(
        sensor.experiments,
        key=lambda e: e.start_time or e.created_at,
        reverse=True,
    )
    return render(request, "sensor_detail.html", {
        "sensor": sensor, "unidades": units, "experimentos": experimentos,
    })


@router.post("/sensores/crear")
def create_sensor(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    mqtt_topic: str = Form(...),
    unit_id: int = Form(0),
    data_type: str = Form("float"),
    min_value: str = Form(""),
    max_value: str = Form(""),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_WRITE)
    name = name.strip()
    if not NAME_RE.match(name):
        return redirect("/sensores", error="Nombre de sensor inválido (2-80, letras/números/_-).")
    mqtt_topic = mqtt_topic.strip()
    if not mqtt_topic:
        return redirect("/sensores", error="El topic MQTT no puede estar vacío.")
    existing = db.query(models.Sensor).filter_by(mqtt_topic=mqtt_topic).first()
    if existing:
        return redirect("/sensores", error=f"Ya existe un sensor con el topic '{mqtt_topic}'.")

    min_v = _parse_float(min_value)
    max_v = _parse_float(max_value)

    sensor = models.Sensor(
        name=name,
        description=description.strip(),
        mqtt_topic=mqtt_topic,
        unit_id=unit_id if unit_id else None,
        data_type=data_type if data_type in TYPES else "float",
        min_value=min_v,
        max_value=max_v,
    )
    db.add(sensor)
    db.commit()
    return redirect(f"/sensores/{sensor.id}", msg=f"Sensor '{name}' creado.")


@router.post("/sensores/{sensor_id}/editar")
def edit_sensor(
    sensor_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    mqtt_topic: str = Form(...),
    unit_id: int = Form(0),
    data_type: str = Form("float"),
    min_value: str = Form(""),
    max_value: str = Form(""),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_WRITE)
    sensor = db.get(models.Sensor, sensor_id)
    if sensor is None:
        return redirect("/sensores", error="Sensor no encontrado.")
    name = name.strip()
    if not NAME_RE.match(name):
        return redirect(f"/sensores/{sensor_id}", error="Nombre inválido.")
    mqtt_topic = mqtt_topic.strip()
    if not mqtt_topic:
        return redirect(f"/sensores/{sensor_id}", error="El topic MQTT no puede estar vacío.")
    existing = (
        db.query(models.Sensor)
        .filter(models.Sensor.mqtt_topic == mqtt_topic, models.Sensor.id != sensor_id)
        .first()
    )
    if existing:
        return redirect(f"/sensores/{sensor_id}", error=f"Ya existe un sensor con el topic '{mqtt_topic}'.")

    sensor.name = name
    sensor.description = description.strip()
    sensor.mqtt_topic = mqtt_topic
    sensor.unit_id = unit_id if unit_id else None
    sensor.data_type = data_type if data_type in TYPES else "float"
    sensor.min_value = _parse_float(min_value)
    sensor.max_value = _parse_float(max_value)
    db.commit()
    return redirect(f"/sensores/{sensor_id}", msg=f"Sensor '{name}' actualizado.")


@router.post("/sensores/{sensor_id}/toggle")
def toggle_sensor(sensor_id: int, request: Request, db: Session = Depends(get_db)):
    require_roles(request, ROLE_WRITE)
    sensor = db.get(models.Sensor, sensor_id)
    if sensor is None:
        return redirect("/sensores", error="Sensor no encontrado.")
    sensor.is_active = not sensor.is_active
    db.commit()
    estado = "activado" if sensor.is_active else "desactivado"
    return redirect(f"/sensores/{sensor_id}", msg=f"Sensor '{sensor.name}' {estado}.")


@router.post("/sensores/{sensor_id}/eliminar")
def delete_sensor(sensor_id: int, request: Request, db: Session = Depends(get_db)):
    require_roles(request, ROLE_WRITE)
    sensor = db.get(models.Sensor, sensor_id)
    if sensor is None:
        return redirect("/sensores", error="Sensor no encontrado.")
    name = sensor.name
    db.delete(sensor)
    db.commit()
    return redirect("/sensores", msg=f"Sensor '{name}' eliminado.")


def _parse_float(value: str):
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
