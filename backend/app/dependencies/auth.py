from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access": raise ValueError
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    user = await db.get(User, user_id)
    if not user or user.account_status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")
    return user


async def optional_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db)) -> User | None:
    if not credentials: return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access": return None
        return await db.get(User, int(payload["sub"]))
    except Exception:
        return None


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin access required")
    return user
