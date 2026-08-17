# 🌍 Global Help Network

A people-helping-people platform built around **ASK → HELP → SOLVE → TRUST**.

## Stack
- Python 3.12+
- FastAPI + Uvicorn
- SQLAlchemy 2 async + asyncpg
- PostgreSQL 15+
- Pydantic v2
- bcrypt + PyJWT
- Jinja2 + Tailwind CDN + vanilla JavaScript
- pytest + pytest-asyncio + httpx

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS
uvicorn app.main:app --reload --app-dir backend
```

Set `DATABASE_URL` and `JWT_SECRET_KEY` in `.env` before starting. The application creates SQLAlchemy tables on startup for local development.

## Seed categories and create admin

```bash
cd backend
python -m scripts.seed_categories
python -m scripts.create_admin --email admin@example.com --username admin --password 'ChangeMe123!'
```

The requested category set contains 11 categories: Technology, Education, Jobs & Career, Travel, Local Help, Housing, Shopping, Transportation, Finance, Daily Life and Other.

## API
- `/health`
- `/health/db`
- `/docs`
- `/redoc`
- `/api/v1/auth/*`
- `/api/v1/users/*`
- `/api/v1/categories`
- `/api/v1/help-requests/*`
- `/api/v1/feed`
- `/api/v1/answers/*`
- `/api/v1/notifications/*`
- `/api/v1/conversations/*`
- `/api/v1/reports`
- `/api/v1/blocks/*`
- `/api/v1/admin/*`

## Frontend
- `/` — feed
- `/login` — login
- `/register` — registration
- `/help-requests/new` — create a request
- `/help-requests?request_id=ID` — request detail
- `/messages` — conversations
- `/notifications` — notifications
- `/admin` — admin dashboard
- `/profile?username=USERNAME` — profile foundation

## Security
Passwords are bcrypt-hashed, refresh tokens are stored as SHA-256 hashes, access/refresh JWTs are rotated, account status is checked on protected routes, and admin endpoints require the admin role.

## Tests

```bash
cd backend
pytest -v --cov=app --cov-report=term-missing
```

## Project status
The repository now contains the runnable application foundation and major core product flows. The supplied specification additionally calls for a larger dedicated route/service/model structure, Alembic migrations and a broad integration test suite; those remain expansion work rather than being represented as fake or placeholder functionality.
