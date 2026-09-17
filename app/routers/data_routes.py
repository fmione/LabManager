import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app import models, realtime, settings as app_settings
from app.auth import SESSION_COOKIE, read_session_token
from app.database import get_db
from app.web import render, require_roles

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


def _query_series(
    db: Session,
    experiment_id: int | None,
    sensor_id: int | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    limit: int,
):
    q = (
        db.query(models.SensorData, models.Sensor)
        .join(models.Sensor, models.SensorData.sensor_id == models.Sensor.id)
    )

    window_from = from_dt
    window_to = to_dt

    if experiment_id:
        exp = db.get(models.Experiment, experiment_id)
        if exp is None:
            return []
        sensor_ids = [s.id for s in exp.sensors]
        if not sensor_ids:
            return []
        q = q.filter(models.Sensor.id.in_(sensor_ids))
        if exp.start_time:
            window_from = max(window_from, exp.start_time) if window_from else exp.start_time
        if exp.end_time:
            window_to = min(window_to, exp.end_time) if window_to else exp.end_time

    if sensor_id:
        q = q.filter(models.SensorData.sensor_id == sensor_id)

    if window_from:
        q = q.filter(models.SensorData.time >= window_from)
    if window_to:
        q = q.filter(models.SensorData.time <= window_to)
    q = q.order_by(models.SensorData.time.asc())

    series = {}
    order = []
    for row, sensor in q.all():
        key = sensor.id
        if key not in series:
            order.append(key)
            unit_label = f" ({sensor.unit.symbol or sensor.unit.name})" if sensor.unit else ""
            series[key] = {
                "sensor_id": sensor.id,
                "label": f"{sensor.name}{unit_label}",
                "name": sensor.name,
                "unit": sensor.unit.symbol or sensor.unit.name if sensor.unit else "",
                "type": sensor.data_type,
                "min_value": sensor.min_value,
                "max_value": sensor.max_value,
                "points": [],
            }
        series[key]["points"].append([int(row.time.timestamp() * 1000), row.value])

    result = []
    for key in order:
        s = series[key]
        pts = s["points"]
        if len(pts) > limit:
            step = len(pts) / limit
            idx = sorted({int(i * step) for i in range(limit)} | {len(pts) - 1})
            pts = [pts[i] for i in idx]
            s["points"] = pts
        result.append(s)
    return result


@router.get("/datos")
def data_page(request: Request, db: Session = Depends(get_db)):
    require_roles(request, {"admin", "investigador", "lector"})
    experiments = db.query(models.Experiment).order_by(models.Experiment.name).all()
    return render(request, "data_viewer.html", {"experimentos": experiments})


@router.get("/api/data")
def api_data(
    request: Request,
    experiment_id: int | None = None,
    sensor_id: int | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    require_roles(request, {"admin", "investigador", "lector"})
    from_provided = from_ is not None
    from_dt = _parse_dt(from_)
    to_dt = _parse_dt(to)
    if (
        from_dt is None
        and to_dt is None
        and not from_provided
        and not (experiment_id or sensor_id)
    ):
        from_dt = datetime.now(timezone.utc) - timedelta(hours=24)
    limit = max(1, min(limit, 5000))
    series = _query_series(db, experiment_id, sensor_id, from_dt, to_dt, limit)
    total = sum(len(s["points"]) for s in series)
    return {"series": series, "total": total}


@router.get("/api/meta")
def api_meta(request: Request, db: Session = Depends(get_db)):
    require_roles(request, {"admin", "investigador", "lector"})
    experiments = db.query(models.Experiment).order_by(models.Experiment.name).all()
    all_sensors = db.query(models.Sensor).order_by(models.Sensor.name).all()
    data = []
    for e in experiments:
        exp_sensors = [
            {
                "id": s.id,
                "name": s.name,
                "unit": s.unit.symbol or s.unit.name if s.unit else "",
                "type": s.data_type,
            }
            for s in e.sensors
        ]
        data.append({
            "id": e.id,
            "name": e.name,
            "start": int(e.start_time.timestamp() * 1000) if e.start_time else None,
            "end": int(e.end_time.timestamp() * 1000) if e.end_time else None,
            "sensors": exp_sensors,
        })
    sensors = [
        {
            "id": s.id,
            "name": s.name,
            "unit": s.unit.symbol or s.unit.name if s.unit else "",
            "type": s.data_type,
        }
        for s in all_sensors
    ]
    return {"experiments": data, "sensors": sensors}


@router.get("/api/data/csv")
def api_data_csv(
    request: Request,
    experiment_id: int | None = None,
    sensor_id: int | None = None,
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = None,
    limit: int = 10000,
    columns: str = "experimento,tiempo,sensor,unidad,valor",
    db: Session = Depends(get_db),
):
    require_roles(request, {"admin", "investigador", "lector"})
    from_provided = from_ is not None
    from_dt = _parse_dt(from_)
    to_dt = _parse_dt(to)
    if (
        from_dt is None
        and to_dt is None
        and not from_provided
        and not (experiment_id or sensor_id)
    ):
        from_dt = datetime.now(timezone.utc) - timedelta(hours=24)
    limit = max(1, min(limit, 100000))
    series = _query_series(db, experiment_id, sensor_id, from_dt, to_dt, limit)

    allowed = {"experimento", "tiempo", "sensor", "unidad", "valor"}
    columns = [c.strip() for c in columns.split(",") if c.strip()]
    selected = [c for c in ["experimento", "tiempo", "sensor", "unidad", "valor"] if c in columns]
    if not selected:
        selected = ["experimento", "tiempo", "sensor", "unidad", "valor"]

    header = selected

    if "experimento" in selected:
        exp_by_sensor: dict[int, list[tuple[str, datetime | None, datetime | None]]] = {}
        rows = (
            db.query(
                models.ExperimentSensor.sensor_id,
                models.Experiment.name,
                models.Experiment.start_time,
                models.Experiment.end_time,
            )
            .join(models.Experiment, models.Experiment.id == models.ExperimentSensor.experiment_id)
            .all()
        )
        for sid, ename, estart, eend in rows:
            exp_by_sensor.setdefault(sid, []).append((ename, estart, eend))
        if experiment_id is not None:
            exp = db.get(models.Experiment, experiment_id)
            exp_name = exp.name if exp else ""
        else:
            exp_name = ""

    lines = [",".join(header)]
    for s in series:
        for ts_ms, value in s["points"]:
            ts_dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            iso = ts_dt.astimezone(app_settings.timezone()).isoformat()
            if s["type"] == "bool":
                value_txt = "True" if value == 1.0 else "False"
            else:
                value_txt = repr(value)
            if "experimento" in selected:
                if experiment_id is not None:
                    exp_label = exp_name
                else:
                    exp_label = ""
                    for ename, estart, eend in exp_by_sensor.get(s["sensor_id"], ()):
                        if estart is not None and ts_dt < estart:
                            continue
                        if eend is not None and ts_dt > eend:
                            continue
                        exp_label = ename
                        break
            else:
                exp_label = ""
            fields = {
                "experimento": exp_label,
                "tiempo": iso,
                "sensor": s["name"],
                "unidad": s["unit"],
                "valor": value_txt,
            }
            lines.append(",".join(fields[c] for c in selected))
    content = "\n".join(lines)
    return PlainTextResponse(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=datos.csv"},
    )


@router.websocket("/ws/data")
async def ws_data(websocket: WebSocket):
    token = websocket.cookies.get(SESSION_COOKIE)
    user = read_session_token(token) if token else None
    if user is None or user["role"] not in {"admin", "investigador", "lector"}:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    realtime.set_loop(asyncio.get_running_loop())
    queue = realtime.subscribe()
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        realtime.unsubscribe(queue)
