from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import models
from app.auth import make_session_token, verify_password
from app.database import get_db
from app.web import current_user, render

router = APIRouter()

SESSION_COOKIE = "lm_session"


@router.get("/login")
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html")


@router.post("/login")
def do_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter_by(username=username).first()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return render(request, "login.html", {"error": "Usuario o contraseña incorrectos."}, status_code=401)

    response = RedirectResponse("/", status_code=303)
    token = make_session_token(user.id, user.role)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=None,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response
