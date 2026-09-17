from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app import models, settings as app_settings
from app.auth import ROLE_WRITE
from app.database import get_db
from app.web import redirect, render, require_roles

router = APIRouter()


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=app_settings.timezone())
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


@router.get("/experimentos")
def experiments_page(request: Request, db: Session = Depends(get_db)):
    require_roles(request, {"admin", "investigador", "lector"})
    experiments = db.query(models.Experiment).order_by(
        models.Experiment.start_time.desc().nulls_last()
    ).all()
    return render(request, "experiments.html", {"experimentos": experiments})


@router.post("/experimentos/crear")
def create_experiment(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_WRITE)
    name = name.strip()
    if not name:
        return redirect("/experimentos", error="El nombre no puede estar vacío.")
    if db.query(models.Experiment).filter_by(name=name).first():
        return redirect("/experimentos", error=f"Ya existe un experimento '{name}'.")

    st = _parse_dt(start_time)
    et = _parse_dt(end_time)
    if st and et and et <= st:
        return redirect("/experimentos", error="La fecha de fin debe ser posterior al inicio.")

    db.add(models.Experiment(name=name, description=description.strip(), start_time=st, end_time=et))
    db.commit()
    return redirect("/experimentos", msg=f"Experimento '{name}' creado.")


@router.get("/experimentos/{experiment_id}")
def experiment_detail(
    experiment_id: int, request: Request, db: Session = Depends(get_db)
):
    require_roles(request, {"admin", "investigador", "lector"})
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        return redirect("/experimentos", error="Experimento no encontrado.")
    all_sensors = db.query(models.Sensor).order_by(models.Sensor.name).all()
    return render(request, "experiment_detail.html", {
        "exp": experiment,
        "all_sensors": all_sensors,
    })


@router.post("/experimentos/{experiment_id}/editar")
def edit_experiment(
    experiment_id: int,
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_WRITE)
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        return redirect("/experimentos", error="Experimento no encontrado.")
    name = name.strip()
    if not name:
        return redirect(f"/experimentos/{experiment_id}", error="El nombre no puede estar vacío.")
    existing = (
        db.query(models.Experiment)
        .filter_by(name=name)
        .filter(models.Experiment.id != experiment_id)
        .first()
    )
    if existing:
        return redirect(f"/experimentos/{experiment_id}", error=f"Ya existe un experimento '{name}'.")

    st = _parse_dt(start_time)
    et = _parse_dt(end_time)
    if st and et and et <= st:
        return redirect(f"/experimentos/{experiment_id}", error="La fecha de fin debe ser posterior al inicio.")

    experiment.name = name
    experiment.description = description.strip()
    experiment.start_time = st
    experiment.end_time = et
    db.commit()
    return redirect(f"/experimentos/{experiment_id}", msg=f"Experimento '{name}' actualizado.")


@router.post("/experimentos/{experiment_id}/asociar")
def associate_sensor(
    experiment_id: int,
    request: Request,
    sensor_id: int = Form(...),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_WRITE)
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        return redirect("/experimentos", error="Experimento no encontrado.")
    sensor = db.get(models.Sensor, sensor_id)
    if sensor is None:
        return redirect(f"/experimentos/{experiment_id}", error="Sensor no encontrado.")
    already = (
        db.query(models.ExperimentSensor)
        .filter_by(experiment_id=experiment_id, sensor_id=sensor_id)
        .first()
    )
    if already:
        return redirect(f"/experimentos/{experiment_id}", error=f"El sensor '{sensor.name}' ya está asociado.")
    db.add(models.ExperimentSensor(experiment_id=experiment_id, sensor_id=sensor_id))
    db.commit()
    return redirect(f"/experimentos/{experiment_id}", msg=f"Sensor '{sensor.name}' asociado.")


@router.post("/experimentos/{experiment_id}/desasociar/{sensor_id}")
def disassociate_sensor(
    experiment_id: int,
    sensor_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_WRITE)
    link = (
        db.query(models.ExperimentSensor)
        .filter_by(experiment_id=experiment_id, sensor_id=sensor_id)
        .first()
    )
    if link:
        db.delete(link)
        db.commit()
    return redirect(f"/experimentos/{experiment_id}", msg="Sensor desasociado.")


@router.post("/experimentos/{experiment_id}/eliminar")
def delete_experiment(
    experiment_id: int, request: Request, db: Session = Depends(get_db)
):
    require_roles(request, ROLE_WRITE)
    experiment = db.get(models.Experiment, experiment_id)
    if experiment is None:
        return redirect("/experimentos", error="Experimento no encontrado.")
    name = experiment.name
    db.delete(experiment)
    db.commit()
    return redirect("/experimentos", msg=f"Experimento '{name}' eliminado.")
