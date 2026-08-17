from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import Base, engine, get_db
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, token_hash, verify_password
from app.dependencies.auth import get_current_user, optional_user, require_admin
from app.models import Answer, Category, Comment, Conversation, HelpfulVote, HelpRequest, Message, Notification, RefreshToken, Report, ReputationEvent, User, UserBlock
from app.schemas import AnswerIn, BlockIn, CommentIn, ConversationIn, LoginIn, MessageIn, PasswordChange, RefreshIn, RegisterIn, ReportIn, RequestIn, StatusIn, UserUpdate, public_user, request_out, user_out

BASE = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE / "../templates"))
app = FastAPI(title="Global Help Network", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()] or ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup() -> None:
    # Keep schema creation as a safety net for a fresh production database.
    # Existing databases should still be managed with migrations.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    # Never leak credentials/connection strings to the browser.
    return JSONResponse(status_code=503, content={"success": False, "detail": "DATABASE_UNAVAILABLE"})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"success": False, "detail": exc.errors()})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "message": "Global Help Network API is running"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(select(func.count()).select_from(User))
    return {"status": "ok", "database": "connected"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("feed.html", {"request": request})


@app.get("/{page}", response_class=HTMLResponse)
async def pages(request: Request, page: str):
    allowed = {"login": "login.html", "register": "register.html", "messages": "messages.html", "notifications": "notifications.html", "admin": "admin.html", "profile": "profile.html", "help-requests": "request.html"}
    if page in allowed:
        return templates.TemplateResponse(allowed[page], {"request": request})
    raise HTTPException(404, "Page not found")


def ok(data: object, meta: dict | None = None) -> dict:
    out = {"success": True, "data": data}
    if meta:
        out["meta"] = meta
    return out


def page_meta(page: int, size: int, total: int) -> dict:
    return {"page": page, "page_size": size, "total": total, "pages": (total + size - 1) // size}


@app.post("/api/v1/auth/register", status_code=201)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()
    username = payload.username.strip()
    if await db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "DUPLICATE_EMAIL")
    if await db.scalar(select(User).where(func.lower(User.username) == username.lower())):
        raise HTTPException(409, "DUPLICATE_USERNAME")

    user = User(
        name=payload.name.strip(),
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
        country=payload.country.strip(),
        city=payload.city.strip(),
        skills=[],
        interests=[],
    )
    db.add(user)
    try:
        await db.flush()
        access = create_access_token(user.id, user.role)
        refresh, expires = create_refresh_token(user.id)
        db.add(RefreshToken(user_id=user.id, token_hash=token_hash(refresh), expires_at=expires))
        await db.commit()
        await db.refresh(user)
    except IntegrityError as exc:
        await db.rollback()
        message = str(exc.orig).lower()
        if "email" in message:
            raise HTTPException(409, "DUPLICATE_EMAIL") from exc
        if "username" in message:
            raise HTTPException(409, "DUPLICATE_USERNAME") from exc
        raise HTTPException(409, "ACCOUNT_ALREADY_EXISTS") from exc

    return ok({"user": user_out(user), "access_token": access, "refresh_token": refresh, "token_type": "bearer"})


@app.post("/api/v1/auth/login")
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    login_value = payload.login.strip().lower()
    user = await db.scalar(select(User).where(or_(func.lower(User.email) == login_value, func.lower(User.username) == login_value)))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if user.account_status != "active":
        raise HTTPException(403, "Account is not active")
    user.last_login_at = datetime.now(timezone.utc)
    access = create_access_token(user.id, user.role)
    refresh, expires = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash(refresh), expires_at=expires))
    await db.commit()
    return ok({"user": user_out(user), "access_token": access, "refresh_token": refresh, "token_type": "bearer"})


@app.post("/api/v1/auth/refresh")
async def refresh(payload: RefreshIn, db: AsyncSession = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError
    except Exception as exc:
        raise HTTPException(401, "TOKEN_INVALID") from exc
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(payload.refresh_token), RefreshToken.revoked_at.is_(None)))
    if not token or token.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, "TOKEN_EXPIRED")
    user = await db.get(User, token.user_id)
    if not user or user.account_status != "active":
        raise HTTPException(403, "Account is not active")
    token.revoked_at = datetime.now(timezone.utc)
    access = create_access_token(user.id, user.role)
    new_refresh, expires = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash(new_refresh), expires_at=expires))
    await db.commit()
    return ok({"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"})


@app.post("/api/v1/auth/logout")
async def logout(payload: RefreshIn, db: AsyncSession = Depends(get_db)):
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash(payload.refresh_token)))
    if token:
        token.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return ok({"logged_out": True})


@app.get("/api/v1/users/me")
async def me(user: User = Depends(get_current_user)):
    return ok(user_out(user))


@app.put("/api/v1/users/me")
async def update_me(payload: UserUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    await db.commit()
    return ok(user_out(user))


@app.patch("/api/v1/users/me/password", status_code=204)
async def change_password(payload: PasswordChange, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    await db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    await db.commit()


@app.get("/api/v1/users/{username}")
async def public_profile(username: str, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(func.lower(User.username) == username.lower(), User.deleted_at.is_(None)))
    if not user:
        raise HTTPException(404, "NOT_FOUND")
    return ok(public_user(user))


@app.get("/api/v1/categories")
async def categories(db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.name))).all()
    return ok([{"id": x.id, "name": x.name, "slug": x.slug, "description": x.description, "icon": x.icon} for x in rows])


@app.post("/api/v1/help-requests", status_code=201)
async def create_request(payload: RequestIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    category = await db.get(Category, payload.category_id)
    if not category or not category.is_active:
        raise HTTPException(422, "Invalid category")
    item = HelpRequest(**payload.model_dump(), created_by=user.id, country=payload.country or user.country, city=payload.city or user.city)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ok(request_out(item, user))


@app.get("/api/v1/help-requests")
async def list_requests(page: int = 1, page_size: int = 20, category_id: int | None = None, country: str | None = None, city: str | None = None, status_filter: str | None = None, urgency: str | None = None, help_type: str | None = None, q: str | None = None, db: AsyncSession = Depends(get_db)):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    conditions = []
    if category_id:
        conditions.append(HelpRequest.category_id == category_id)
    if country:
        conditions.append(func.lower(HelpRequest.country) == country.lower())
    if city:
        conditions.append(func.lower(HelpRequest.city) == city.lower())
    if status_filter:
        conditions.append(HelpRequest.status == status_filter)
    if urgency:
        conditions.append(HelpRequest.urgency == urgency)
    if help_type:
        conditions.append(HelpRequest.help_type == help_type)
    if q:
        conditions.append(or_(HelpRequest.title.ilike(f"%{q}%"), HelpRequest.description.ilike(f"%{q}%")))
    total = await db.scalar(select(func.count()).select_from(HelpRequest).where(and_(*conditions)))
    rows = (await db.scalars(select(HelpRequest).where(and_(*conditions)).order_by(HelpRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    users = {u.id: u for u in (await db.scalars(select(User).where(User.id.in_([r.created_by for r in rows])))).all()} if rows else {}
    return ok([request_out(r, users.get(r.created_by)) for r in rows], page_meta(page, page_size, total or 0))


@app.get("/api/v1/help-requests/{request_id}")
async def get_request(request_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(HelpRequest, request_id)
    if not item:
        raise HTTPException(404, "NOT_FOUND")
    author = await db.get(User, item.created_by)
    answers_count = await db.scalar(select(func.count()).select_from(Answer).where(Answer.request_id == item.id))
    comments_count = await db.scalar(select(func.count()).select_from(Comment).where(Comment.request_id == item.id, Comment.is_deleted.is_(False)))
    data = request_out(item, author)
    data.update({"answers_count": answers_count or 0, "comments_count": comments_count or 0})
    return ok(data)


@app.put("/api/v1/help-requests/{request_id}")
async def edit_request(request_id: int, payload: RequestIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(HelpRequest, request_id)
    if not item:
        raise HTTPException(404, "NOT_FOUND")
    if item.created_by != user.id and user.role != "admin":
        raise HTTPException(403, "FORBIDDEN")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return ok(request_out(item, user))


@app.delete("/api/v1/help-requests/{request_id}", status_code=204)
async def delete_request(request_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(HelpRequest, request_id)
    if not item:
        raise HTTPException(404, "NOT_FOUND")
    if item.created_by != user.id and user.role != "admin":
        raise HTTPException(403, "FORBIDDEN")
    await db.delete(item)
    await db.commit()


@app.patch("/api/v1/help-requests/{request_id}/in-progress")
async def in_progress(request_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(HelpRequest, request_id)
    if not item or item.created_by != user.id:
        raise HTTPException(403, "FORBIDDEN")
    if item.status != "Open":
        raise HTTPException(422, "Only Open requests can move to In Progress")
    item.status = "In Progress"
    await db.commit()
    return ok(request_out(item, user))


@app.patch("/api/v1/help-requests/{request_id}/solve")
async def solve(request_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(HelpRequest, request_id)
    if not item or item.created_by != user.id:
        raise HTTPException(403, "FORBIDDEN")
    if item.status == "Solved":
        return ok(request_out(item, user))
    if item.status == "Closed":
        raise HTTPException(422, "Closed requests cannot be solved")
    item.status = "Solved"
    item.solved_at = datetime.now(timezone.utc)
    user.solved_requests_count += 1
    user.reputation_score += 15
    db.add(ReputationEvent(user_id=user.id, action="request_solved", points=15, entity_type="help_request", entity_id=item.id))
    await db.commit()
    return ok(request_out(item, user))


@app.patch("/api/v1/help-requests/{request_id}/close")
async def close(request_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(HelpRequest, request_id)
    if not item:
        raise HTTPException(404, "NOT_FOUND")
    if item.created_by != user.id and user.role != "admin":
        raise HTTPException(403, "FORBIDDEN")
    item.status = "Closed"
    item.closed_at = datetime.now(timezone.utc)
    await db.commit()
    return ok(request_out(item, user))


@app.get("/api/v1/feed")
async def feed(mode: str = "newest", page: int = 1, page_size: int = 20, category_id: int | None = None, user: User | None = Depends(optional_user), db: AsyncSession = Depends(get_db)):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    query = select(HelpRequest).where(HelpRequest.status != "Closed")
    if mode == "unanswered":
        query = query.where(HelpRequest.status == "Open", ~HelpRequest.id.in_(select(Answer.request_id)))
    elif mode == "nearby":
        if user:
            query = query.where(HelpRequest.country == user.country, HelpRequest.city == user.city)
        else:
            query = query.where(False)
    elif mode == "category":
        if not category_id:
            raise HTTPException(422, "category_id is required")
        query = query.where(HelpRequest.category_id == category_id)
    query = query.order_by(HelpRequest.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.scalars(query)).all()
    authors = {u.id: u for u in (await db.scalars(select(User).where(User.id.in_([r.created_by for r in rows])))).all()} if rows else {}
    return ok([request_out(r, authors.get(r.created_by)) for r in rows], page_meta(page, page_size, len(rows)))


# Remaining application routes intentionally stay unchanged below this point.
