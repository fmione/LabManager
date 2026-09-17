import re

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app import models
from app.auth import ROLE_ADMIN, ROLE_LABELS, hash_password
from app.database import get_db
from app.web import redirect, render, require_roles

router = APIRouter()

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


@router.get("/usuarios")
def users_page(request: Request, db: Session = Depends(get_db)):
    require_roles(request, ROLE_ADMIN)
    users = db.query(models.User).order_by(models.User.created_at).all()
    return render(request, "users.html", {"usuarios": users, "role_labels": ROLE_LABELS})


@router.post("/usuarios/crear")
def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_ADMIN)
    if role not in ROLE_LABELS:
        return redirect("/usuarios", error="Rol inválido.")
    if not USERNAME_RE.match(username):
        return redirect("/usuarios", error="Nombre de usuario inválido (3-50 caracteres, letras/números/._-).")
    if len(password) < 6:
        return redirect("/usuarios", error="La contraseña debe tener al menos 6 caracteres.")
    if db.query(models.User).filter_by(username=username).first():
        return redirect("/usuarios", error=f"El usuario '{username}' ya existe.")
    if db.query(models.User).filter_by(email=email).first():
        return redirect("/usuarios", error=f"El email '{email}' ya está registrado.")

    db.add(models.User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
    ))
    db.commit()
    return redirect("/usuarios", msg=f"Usuario '{username}' creado.")


@router.post("/usuarios/{user_id}/toggle")
def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = require_roles(request, ROLE_ADMIN)
    user = db.get(models.User, user_id)
    if user is None:
        return redirect("/usuarios", error="Usuario no encontrado.")
    if user.id == admin["uid"]:
        return redirect("/usuarios", error="No podés desactivar tu propio usuario.")
    user.is_active = not user.is_active
    db.commit()
    estado = "activado" if user.is_active else "desactivado"
    return redirect("/usuarios", msg=f"Usuario '{user.username}' {estado}.")


@router.post("/usuarios/{user_id}/editar")
def edit_user(
    user_id: int,
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    require_roles(request, ROLE_ADMIN)
    user = db.get(models.User, user_id)
    if user is None:
        return redirect("/usuarios", error="Usuario no encontrado.")
    if role not in ROLE_LABELS:
        return redirect("/usuarios", error="Rol inválido.")
    if not USERNAME_RE.match(username):
        return redirect("/usuarios", error="Nombre de usuario inválido (3-50 caracteres, letras/números/._-).")
    existing = db.query(models.User).filter(models.User.username == username).first()
    if existing and existing.id != user_id:
        return redirect("/usuarios", error=f"El usuario '{username}' ya existe.")
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing and existing.id != user_id:
        return redirect("/usuarios", error=f"El email '{email}' ya está registrado.")
    if password and len(password) < 6:
        return redirect("/usuarios", error="La contraseña debe tener al menos 6 caracteres.")

    user.username = username
    user.email = email
    user.role = role
    if password:
        user.password_hash = hash_password(password)
    db.commit()
    return redirect("/usuarios", msg=f"Usuario '{username}' actualizado.")


@router.post("/usuarios/{user_id}/eliminar")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = require_roles(request, ROLE_ADMIN)
    user = db.get(models.User, user_id)
    if user is None:
        return redirect("/usuarios", error="Usuario no encontrado.")
    if user.id == admin["uid"]:
        return redirect("/usuarios", error="No podés eliminar tu propio usuario.")
    db.delete(user)
    db.commit()
    return redirect("/usuarios", msg=f"Usuario '{user.username}' eliminado.")
