from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Envelope(BaseModel):
    success: bool = True
    data: object


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_.]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    country: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not (any(c.isupper() for c in value) and any(c.islower() for c in value) and any(c.isdigit() for c in value) and any(not c.isalnum() for c in value)):
            raise ValueError("Password must contain upper, lower, digit and special character")
        return value


class LoginIn(BaseModel):
    login: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    bio: str | None = None
    country: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    skills: list[str] | None = None
    interests: list[str] | None = None
    profile_picture_url: str | None = Field(default=None, max_length=500)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class RequestIn(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10)
    category_id: int
    location: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    help_type: str = "Both"
    urgency: str = "Medium"
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("help_type")
    @classmethod
    def help_type_valid(cls, v: str) -> str:
        if v not in {"Online", "Local", "Both"}: raise ValueError("Invalid help_type")
        return v

    @field_validator("urgency")
    @classmethod
    def urgency_valid(cls, v: str) -> str:
        if v not in {"Low", "Medium", "High"}: raise ValueError("Invalid urgency")
        return v


class AnswerIn(BaseModel):
    content: str = Field(min_length=2)


class CommentIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class ConversationIn(BaseModel):
    receiver_id: int


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class ReportIn(BaseModel):
    target_type: str
    target_id: int
    reason: str = Field(max_length=100)
    description: str | None = None


class BlockIn(BaseModel):
    blocked_id: int


class StatusIn(BaseModel):
    status: str
    review_note: str | None = None


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=120)
    description: str | None = None
    icon: str | None = None
    is_active: bool = True
    sort_order: int = 0


def user_out(user: object) -> dict:
    return {"id": user.id, "name": user.name, "username": user.username, "email": user.email, "country": user.country, "city": user.city, "bio": user.bio, "skills": user.skills or [], "interests": user.interests or [], "profile_picture_url": user.profile_picture_url, "reputation_score": user.reputation_score, "helpful_answers_count": user.helpful_answers_count, "solved_requests_count": user.solved_requests_count, "role": user.role, "account_status": user.account_status}


def public_user(user: object) -> dict:
    data = user_out(user); data.pop("email", None); return data


def request_out(item: object, author: object | None = None) -> dict:
    return {"id": item.id, "title": item.title, "description": item.description, "category_id": item.category_id, "location": item.location, "country": item.country, "city": item.city, "help_type": item.help_type, "urgency": item.urgency, "tags": item.tags or [], "status": item.status, "created_by": item.created_by, "created_at": item.created_at, "updated_at": item.updated_at, "author": public_user(author) if author else None}
