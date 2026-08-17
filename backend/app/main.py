from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, delete, func, or_, select, update
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
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",") if x.strip()], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
    if await db.scalar(select(User).where(func.lower(User.email) == payload.email.lower())):
        raise HTTPException(409, "DUPLICATE_EMAIL")
    if await db.scalar(select(User).where(func.lower(User.username) == payload.username.lower())):
        raise HTTPException(409, "DUPLICATE_USERNAME")
    user = User(name=payload.name, username=payload.username, email=payload.email, password_hash=hash_password(payload.password), country=payload.country, city=payload.city)
    db.add(user)
    await db.flush()
    access = create_access_token(user.id, user.role)
    refresh, expires = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=token_hash(refresh), expires_at=expires))
    await db.commit()
    return ok({"user": user_out(user), "access_token": access, "refresh_token": refresh, "token_type": "bearer"})


@app.post("/api/v1/auth/login")
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(or_(func.lower(User.email) == payload.login.lower(), func.lower(User.username) == payload.login.lower())))
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


@app.post("/api/v1/help-requests/{request_id}/answers", status_code=201)
async def add_answer(request_id: int, payload: AnswerIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(HelpRequest, request_id)
    if not item:
        raise HTTPException(404, "NOT_FOUND")
    if item.created_by == user.id:
        raise HTTPException(403, "FORBIDDEN")
    if item.status not in {"Open", "In Progress"}:
        raise HTTPException(403, "Request is closed")
    answer = Answer(request_id=request_id, user_id=user.id, content=payload.content)
    db.add(answer)
    user.reputation_score += 5
    db.add(ReputationEvent(user_id=user.id, action="answer_submitted", points=5, entity_type="answer", entity_id=request_id))
    db.add(Notification(user_id=item.created_by, actor_id=user.id, type="answer_received", title="New answer", body=f"{user.username} answered your request", entity_type="help_request", entity_id=request_id))
    await db.commit()
    await db.refresh(answer)
    return ok({"id": answer.id, "request_id": answer.request_id, "user_id": answer.user_id, "content": answer.content, "is_best_answer": answer.is_best_answer, "helpful_count": answer.helpful_count, "created_at": answer.created_at})


@app.get("/api/v1/help-requests/{request_id}/answers")
async def answers(request_id: int, page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db)):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    rows = (await db.scalars(select(Answer).where(Answer.request_id == request_id).order_by(Answer.is_best_answer.desc(), Answer.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    return ok([{"id": a.id, "request_id": a.request_id, "user_id": a.user_id, "content": a.content, "is_best_answer": a.is_best_answer, "helpful_count": a.helpful_count, "created_at": a.created_at} for a in rows], page_meta(page, page_size, len(rows)))


@app.patch("/api/v1/answers/{answer_id}/best")
async def best_answer(answer_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    answer = await db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(404, "NOT_FOUND")
    request = await db.get(HelpRequest, answer.request_id)
    if not request or request.created_by != user.id or answer.user_id == user.id:
        raise HTTPException(403, "FORBIDDEN")
    if answer.is_best_answer:
        return ok({"id": answer.id, "is_best_answer": True})
    await db.execute(update(Answer).where(Answer.request_id == request.id).values(is_best_answer=False))
    answer.is_best_answer = True
    owner = await db.get(User, answer.user_id)
    if owner:
        owner.reputation_score += 25
        db.add(ReputationEvent(user_id=owner.id, action="best_answer", points=25, entity_type="answer", entity_id=answer.id))
        db.add(Notification(user_id=owner.id, actor_id=user.id, type="best_answer", title="Best answer", body="Your answer was selected as best", entity_type="answer", entity_id=answer.id))
    await db.commit()
    return ok({"id": answer.id, "is_best_answer": True})


@app.post("/api/v1/answers/{answer_id}/helpful")
async def helpful(answer_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    answer = await db.get(Answer, answer_id)
    if not answer:
        raise HTTPException(404, "NOT_FOUND")
    if answer.user_id == user.id:
        raise HTTPException(403, "FORBIDDEN")
    if await db.scalar(select(HelpfulVote).where(HelpfulVote.answer_id == answer_id, HelpfulVote.user_id == user.id)):
        raise HTTPException(409, "CONFLICT")
    db.add(HelpfulVote(answer_id=answer_id, user_id=user.id))
    answer.helpful_count += 1
    owner = await db.get(User, answer.user_id)
    if owner:
        owner.reputation_score += 10
        owner.helpful_answers_count += 1
        db.add(ReputationEvent(user_id=owner.id, action="answer_helpful", points=10, entity_type="answer", entity_id=answer.id))
    await db.commit()
    return ok({"voted": True, "helpful_count": answer.helpful_count})


@app.delete("/api/v1/answers/{answer_id}/helpful")
async def unhelpful(answer_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    vote = await db.scalar(select(HelpfulVote).where(HelpfulVote.answer_id == answer_id, HelpfulVote.user_id == user.id))
    if vote:
        answer = await db.get(Answer, answer_id)
        if answer:
            owner = await db.get(User, answer.user_id)
            await db.delete(vote)
            answer.helpful_count = max(0, answer.helpful_count - 1)
            if owner:
                owner.reputation_score = max(0, owner.reputation_score - 10)
                owner.helpful_answers_count = max(0, owner.helpful_answers_count - 1)
        await db.commit()
    return ok({"voted": False})


@app.get("/api/v1/answers/{answer_id}/helpful/status")
async def helpful_status(answer_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok({"voted": bool(await db.scalar(select(HelpfulVote.id).where(HelpfulVote.answer_id == answer_id, HelpfulVote.user_id == user.id)))})


@app.post("/api/v1/help-requests/{request_id}/comments", status_code=201)
async def request_comment(request_id: int, payload: CommentIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    item = await db.get(HelpRequest, request_id)
    if not item:
        raise HTTPException(404, "NOT_FOUND")
    comment = Comment(request_id=request_id, user_id=user.id, content=payload.content)
    db.add(comment)
    if item.created_by != user.id:
        db.add(Notification(user_id=item.created_by, actor_id=user.id, type="comment_received", title="New comment", body=f"{user.username} commented on your request", entity_type="help_request", entity_id=request_id))
    await db.commit()
    await db.refresh(comment)
    return ok({"id": comment.id, "content": comment.content, "user_id": comment.user_id})


@app.get("/api/v1/help-requests/{request_id}/comments")
async def request_comments(request_id: int, db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Comment).where(Comment.request_id == request_id, Comment.is_deleted.is_(False)).order_by(Comment.created_at))).all()
    return ok([{"id": c.id, "content": c.content, "user_id": c.user_id, "created_at": c.created_at} for c in rows])


@app.get("/api/v1/notifications")
async def notifications(unread: bool = False, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread:
        q = q.where(Notification.is_read.is_(False))
    rows = (await db.scalars(q.order_by(Notification.created_at.desc()).limit(100))).all()
    return ok([{"id": n.id, "type": n.type, "title": n.title, "body": n.body, "is_read": n.is_read, "created_at": n.created_at} for n in rows])


@app.get("/api/v1/notifications/unread-count")
async def unread_count(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok({"count": await db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))) or 0})


@app.patch("/api/v1/notifications/{notification_id}/read")
async def mark_read(notification_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    n = await db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(403, "FORBIDDEN")
    n.is_read = True
    await db.commit()
    return ok({"read": True})


@app.patch("/api/v1/notifications/read-all")
async def read_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
    await db.commit()
    return ok({"read_all": True})


@app.post("/api/v1/blocks")
async def block(payload: BlockIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.blocked_id == user.id:
        raise HTTPException(422, "Cannot block yourself")
    if not await db.get(User, payload.blocked_id):
        raise HTTPException(404, "NOT_FOUND")
    if not await db.scalar(select(UserBlock).where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == payload.blocked_id)):
        db.add(UserBlock(blocker_id=user.id, blocked_id=payload.blocked_id))
        await db.commit()
    return ok({"blocked_id": payload.blocked_id})


@app.delete("/api/v1/blocks/{blocked_id}")
async def unblock(blocked_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(UserBlock).where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == blocked_id))
    await db.commit()
    return ok({"blocked_id": blocked_id, "blocked": False})


@app.post("/api/v1/conversations")
async def create_conversation(payload: ConversationIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.receiver_id == user.id:
        raise HTTPException(422, "Cannot message yourself")
    receiver = await db.get(User, payload.receiver_id)
    if not receiver or receiver.deleted_at is not None:
        raise HTTPException(404, "NOT_FOUND")
    blocked = await db.scalar(select(UserBlock).where(or_(and_(UserBlock.blocker_id == user.id, UserBlock.blocked_id == payload.receiver_id), and_(UserBlock.blocker_id == payload.receiver_id, UserBlock.blocked_id == user.id))))
    if blocked:
        raise HTTPException(403, "BLOCKED")
    a, b = sorted((user.id, payload.receiver_id))
    conv = await db.scalar(select(Conversation).where(Conversation.user1_id == a, Conversation.user2_id == b))
    if not conv:
        conv = Conversation(user1_id=a, user2_id=b)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
    return ok({"id": conv.id, "user1_id": conv.user1_id, "user2_id": conv.user2_id})


@app.get("/api/v1/conversations")
async def conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Conversation).where(or_(Conversation.user1_id == user.id, Conversation.user2_id == user.id)).order_by(Conversation.last_message_at.desc().nullslast()))).all()
    return ok([{"id": c.id, "other_user_id": c.user2_id if c.user1_id == user.id else c.user1_id, "last_message_at": c.last_message_at} for c in rows])


@app.get("/api/v1/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await db.get(Conversation, conversation_id)
    if not c or user.id not in {c.user1_id, c.user2_id}:
        raise HTTPException(403, "FORBIDDEN")
    rows = (await db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).limit(100))).all()
    return ok([{"id": m.id, "sender_id": m.sender_id, "receiver_id": m.receiver_id, "content": m.content, "read_at": m.read_at, "created_at": m.created_at} for m in rows])


@app.post("/api/v1/conversations/{conversation_id}/messages", status_code=201)
async def send_message(conversation_id: int, payload: MessageIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    content = payload.content.strip()
    if not content:
        raise HTTPException(422, "Message cannot be empty")
    c = await db.get(Conversation, conversation_id)
    if not c or user.id not in {c.user1_id, c.user2_id}:
        raise HTTPException(403, "FORBIDDEN")
    receiver = c.user2_id if c.user1_id == user.id else c.user1_id
    if await db.scalar(select(UserBlock).where(or_(and_(UserBlock.blocker_id == user.id, UserBlock.blocked_id == receiver), and_(UserBlock.blocker_id == receiver, UserBlock.blocked_id == user.id)))):
        raise HTTPException(403, "BLOCKED")
    msg = Message(conversation_id=conversation_id, sender_id=user.id, receiver_id=receiver, content=content)
    db.add(msg)
    c.last_message_at = datetime.now(timezone.utc)
    db.add(Notification(user_id=receiver, actor_id=user.id, type="message_received", title="New message", body=f"{user.username} sent you a message", entity_type="conversation", entity_id=conversation_id))
    await db.commit()
    await db.refresh(msg)
    return ok({"id": msg.id, "content": msg.content, "sender_id": msg.sender_id, "receiver_id": msg.receiver_id, "created_at": msg.created_at})


@app.patch("/api/v1/conversations/{conversation_id}/read")
async def read_messages(conversation_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await db.get(Conversation, conversation_id)
    if not c or user.id not in {c.user1_id, c.user2_id}:
        raise HTTPException(403, "FORBIDDEN")
    await db.execute(update(Message).where(Message.conversation_id == conversation_id, Message.receiver_id == user.id, Message.read_at.is_(None)).values(read_at=datetime.now(timezone.utc)))
    await db.commit()
    return ok({"read": True})


@app.post("/api/v1/reports", status_code=201)
async def create_report(payload: ReportIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if payload.target_type == "user" and payload.target_id == user.id:
        raise HTTPException(403, "FORBIDDEN")
    existing = await db.scalar(select(Report).where(Report.reporter_id == user.id, Report.target_type == payload.target_type, Report.target_id == payload.target_id, Report.status == "Pending"))
    if existing:
        raise HTTPException(409, "CONFLICT")
    report = Report(reporter_id=user.id, **payload.model_dump())
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return ok({"id": report.id, "status": report.status})


@app.get("/api/v1/admin/dashboard/stats")
async def admin_stats(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    async def count(model, condition=None):
        if condition is None:
            return await db.scalar(select(func.count()).select_from(model))
        return await db.scalar(select(func.count()).select_from(model).where(condition))
    return ok({"total_users": await count(User), "active_users": await count(User, User.account_status == "active"), "suspended_users": await count(User, User.account_status == "suspended"), "total_requests": await count(HelpRequest), "open_requests": await count(HelpRequest, HelpRequest.status == "Open"), "solved_requests": await count(HelpRequest, HelpRequest.status == "Solved"), "pending_reports": await count(Report, Report.status == "Pending")})


@app.get("/api/v1/admin/users")
async def admin_users(page: int = 1, page_size: int = 50, q: str | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    conditions = [User.deleted_at.is_(None)]
    if q:
        conditions.append(or_(User.username.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"), User.name.ilike(f"%{q}%")))
    total = await db.scalar(select(func.count()).select_from(User).where(and_(*conditions)))
    rows = (await db.scalars(select(User).where(and_(*conditions)).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    return ok([user_out(u) for u in rows], page_meta(page, page_size, total or 0))


@app.patch("/api/v1/admin/users/{user_id}/status")
async def admin_user_status(user_id: int, payload: StatusIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    target = await db.get(User, user_id)
    if not target or target.deleted_at is not None:
        raise HTTPException(404, "NOT_FOUND")
    if target.id == admin.id and payload.status != "active":
        raise HTTPException(422, "You cannot disable your own admin account")
    if payload.status not in {"active", "suspended", "banned"}:
        raise HTTPException(422, "Invalid status")
    target.account_status = payload.status
    await db.commit()
    return ok({"id": target.id, "status": target.account_status})


@app.get("/api/v1/admin/reports")
async def admin_reports(page: int = 1, page_size: int = 50, report_status: str | None = None, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    conditions = []
    if report_status:
        conditions.append(Report.status == report_status)
    total = await db.scalar(select(func.count()).select_from(Report).where(and_(*conditions)))
    rows = (await db.scalars(select(Report).where(and_(*conditions)).order_by(Report.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    return ok([{"id": r.id, "reporter_id": r.reporter_id, "target_type": r.target_type, "target_id": r.target_id, "reason": r.reason, "status": r.status, "review_note": r.review_note, "created_at": r.created_at} for r in rows], page_meta(page, page_size, total or 0))


@app.patch("/api/v1/admin/reports/{report_id}")
async def admin_report_status(report_id: int, payload: StatusIn, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "NOT_FOUND")
    if payload.status not in {"Reviewing", "Resolved", "Rejected"}:
        raise HTTPException(422, "Invalid report status")
    report.status = payload.status
    report.reviewed_by = admin.id
    report.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return ok({"id": report.id, "status": report.status})
