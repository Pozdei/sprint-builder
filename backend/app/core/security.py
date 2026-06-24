"""Безопасность: хеш паролей (bcrypt), JWT-токены и шифрование секретов конфига.

bcrypt вызываем напрямую — без passlib, чтобы не тащить лишнюю зависимость.
"""

import hashlib
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


# -------------------- Пароли --------------------

def hash_password(password: str) -> str:
    """Хешировать пароль bcrypt. Соль генерируется автоматически."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# -------------------- JWT --------------------

_ALG = "HS256"


def create_access_token(user_id: int, role: str) -> str:
    """Создать JWT с user_id и role. Срок жизни — settings.jwt_expire_hours."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),       # subject — user id (стандартное поле)
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.jwt_expire_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALG)


class TokenError(Exception):
    """Не валидный/просроченный/повреждённый токен."""


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALG])
    except jwt.ExpiredSignatureError:
        raise TokenError("Token expired")
    except jwt.InvalidTokenError as e:
        raise TokenError(f"Invalid token: {e}")
    return payload


# -------------------- Шифрование секретов (Jira-токен в Config) --------------------
# Ключ Fernet выводим из JWT_SECRET — отдельный ENCRYPTION_KEY не завели,
# чтобы не плодить ещё одну обязательную переменную окружения.

_fernet = Fernet(urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest()))


def encrypt_secret(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str | None:
    """Расшифровать; None если ключ/данные повреждены (например, сменили JWT_SECRET)."""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None
