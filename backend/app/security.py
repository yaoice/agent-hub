# -*- coding: utf-8 -*-
"""安全模块：密码哈希、JWT、Provider 密钥对称加密。"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _fernet() -> Fernet:
    """由 APP_SECRET 派生稳定的 Fernet 密钥，用于加密 Provider secret_key。"""
    digest = hashlib.sha256(settings.app_secret.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return ""


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.app_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.app_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def mask_secret(value: str) -> str:
    """脱敏展示：保留首尾少量字符。"""
    if not value:
        return ""
    if len(value) <= 8:
        return value[0] + "****"
    return f"{value[:4]}****{value[-4:]}"
