from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app import models
from app.auth import ROLE_WRITE
from app.database import get_db
from app.web import redirect, render, require_roles

router = APIRouter()

CATEGORIES = [
    "temperatura", "presion", "volumen", "masa", "tiempo",
    "velocidad", "concentracion", "pH", "flujo", "frecuencia",
    "porcentaje", "otra",
]


@router.get("/unidades")
def units_page(request: Request, db: Session = Depends(get_db)):
    require_roles(request, {"admin", "investigador", "lector"})
    units = db.query(models.Unit).order_by(models.Unit.category, models.Unit.name).all()
    return render(request, "units.html", {"unidades": units, "categories": CATEGORIES})


@router.post("/unidades/crear")
def create_unit(
    request: Request,
    name: str = Form(...),
    symbol: str = Form(...),
    category: str = Form("otra"),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_WRITE)
    name = name.strip()
    symbol = symbol.strip()
    if not name:
        return redirect("/unidades", error="El nombre no puede estar vacío.")
    if not symbol:
        return redirect("/unidades", error="El símbolo no puede estar vacío.")
    if category not in CATEGORIES:
        category = "otra"
    if db.query(models.Unit).filter_by(name=name).first():
        return redirect("/unidades", error=f"Ya existe la unidad '{name}'.")
    db.add(models.Unit(name=name, symbol=symbol, category=category))
    db.commit()
    return redirect("/unidades", msg=f"Unidad '{name}' creada.")


@router.post("/unidades/{unit_id}/editar")
def edit_unit(
    unit_id: int,
    request: Request,
    name: str = Form(...),
    symbol: str = Form(...),
    category: str = Form("otra"),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_WRITE)
    unit = db.get(models.Unit, unit_id)
    if unit is None:
        return redirect("/unidades", error="Unidad no encontrada.")
    name = name.strip()
    symbol = symbol.strip()
    if not name or not symbol:
        return redirect("/unidades", error="Nombre y símbolo son obligatorios.")
    if category not in CATEGORIES:
        category = "otra"
    existing = (
        db.query(models.Unit)
        .filter(models.Unit.name == name, models.Unit.id != unit_id)
        .first()
    )
    if existing:
        return redirect("/unidades", error=f"Ya existe la unidad '{name}'.")
    unit.name = name
    unit.symbol = symbol
    unit.category = category
    db.commit()
    return redirect("/unidades", msg=f"Unidad '{name}' actualizada.")


@router.post("/unidades/{unit_id}/eliminar")
def delete_unit(unit_id: int, request: Request, db: Session = Depends(get_db)):
    require_roles(request, ROLE_WRITE)
    unit = db.get(models.Unit, unit_id)
    if unit is None:
        return redirect("/unidades", error="Unidad no encontrada.")
    name = unit.name
    db.delete(unit)
    db.commit()
    return redirect("/unidades", msg=f"Unidad '{name}' eliminada.")
