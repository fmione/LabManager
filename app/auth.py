from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import SECRET_KEY, SESSION_MAX_AGE

import bcrypt

ROLE_LABELS = {
    "admin": "Administrador",
    "investigador": "Jefe de Laboratorio",
    "lector": "Invitado",
}

ROLE_WRITE = {"admin", "investigador"}
ROLE_ADMIN = {"admin"}

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="labmanager-session")

SESSION_COOKIE = "lm_session"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def make_session_token(user_id: int, role: str) -> str:
    return _serializer.dumps({"uid": user_id, "role": role})


def read_session_token(token: str) -> dict | None:
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
