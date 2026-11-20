"""Пароли и непрозрачные сессионные токены."""

import hashlib
import hmac
import secrets


def hash_password(password: str, salt: str | None = None) -> str:
    """Вычисляет хеш пароля с индивидуальной солью."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1)
    return f"{salt}:{digest.hex()}"


def matches(password: str, stored: str) -> bool:
    """Проверяет пароль сравнением за постоянное время."""
    return hmac.compare_digest(hash_password(password, stored.split(":")[0]), stored)


def token_digest(token: str) -> str:
    """Возвращает идентификатор сессии для хранения в БД."""
    return hashlib.sha256(token.encode()).hexdigest()
