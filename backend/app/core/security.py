import hashlib
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "role": role, "type": "access", "jti": str(uuid.uuid4()), "iat": now, "exp": now + timedelta(minutes=settings.access_token_expire_minutes)}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=settings.refresh_token_expire_days)
    token = jwt.encode({"sub": str(user_id), "type": "refresh", "jti": str(uuid.uuid4()), "iat": now, "exp": expires}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, expires


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
