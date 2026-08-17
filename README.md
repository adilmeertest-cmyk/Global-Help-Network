# 🌍 Global Help Network

A people-helping-people platform built around **ASK → HELP → SOLVE → TRUST**. The repository follows the requested Python/FastAPI + PostgreSQL + Jinja2/Tailwind/vanilla-JS stack. The product specification requires FastAPI, SQLAlchemy async, PostgreSQL, JWT/bcrypt security, responsive pages, messaging, notifications, reputation, reports, blocks, admin tools and tests. fileciteturn4file0L26-L32

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

Set `DATABASE_URL` and `JWT_SECRET_KEY` in `.env` before starting. The application creates its SQLAlchemy tables on startup for local development. For production, use Alembic migrations before deployment.

## Seed categories

```bash
cd backend
python -m scripts.seed_categories
python -m scripts.create_admin --email admin@example.com --username admin --password 'ChangeMe123!'
```

The requested initial category set contains 11 categories: Technology, Education, Jobs & Career, Travel, Local Help, Housing, Shopping, Transportation, Finance, Daily Life and Other. fileciteturn4file0L74-L79

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

The API uses the requested success envelope and pagination convention. fileciteturn4file0L107-L116

## Frontend
- `/` — feed
- `/login` — login
- `/register` — registration
- `/help-requests/new` — create a request
- `/help-requests?request_id=ID` — request detail
- `/messages` — conversations
- `/notifications` — notifications
- `/admin` — admin dashboard
- `/profile?username=USERNAME` — profile endpoint/page foundation

## Security
Passwords are bcrypt-hashed, refresh tokens are stored as SHA-256 hashes, JWT access/refresh tokens are rotated, account status is checked on protected routes, and admin endpoints require the admin role. These are core requirements from the supplied specification. fileciteturn4file0L92-L103

## Tests

```bash
cd backend
pytest -v --cov=app --cov-report=term-missing
```

## Project status
This repository contains the runnable application foundation and the major core product flows from the supplied specification. The supplied specification itself calls for a larger multi-batch implementation, including dedicated route/service/model files, Alembic migrations and a broad integration test suite. fileciteturn4file0L45-L56
