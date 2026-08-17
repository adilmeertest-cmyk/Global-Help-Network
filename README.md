# 🌍 Global Help Network

A premium, responsive people-helping-people platform built around **ASK → HELP → SOLVE → TRUST**.

## Architecture
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS + React Router + Lucide
- **Backend:** Python 3.12 + FastAPI + Uvicorn
- **Database:** PostgreSQL 15+ via SQLAlchemy 2 async + asyncpg
- **Auth:** JWT access/refresh tokens + bcrypt password hashing
- **Frontend/API contract:** typed client, bearer auth, same-origin `/api` in production, Vite proxy locally
- **Deployment:** Vercel-ready React build + Python ASGI function

The supplied product specification requires FastAPI, PostgreSQL, SQLAlchemy async, JWT/bcrypt, responsive UI, feed, requests, answers, reputation, messaging, notifications, reports, blocks, admin tools and tests. fileciteturn4file0L17-L32

## Run locally

### Backend
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS
uvicorn app.main:app --reload --app-dir backend
```

Set `DATABASE_URL`, `JWT_SECRET_KEY`, and (when needed) `CORS_ORIGINS` in `.env`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

The Vite development server proxies `/api` and `/health` to `http://localhost:8000`. For a separate API host, set `VITE_API_URL` in `frontend/.env`.

## Seed categories and create admin
```bash
cd backend
python -m scripts.seed_categories
python -m scripts.create_admin --email admin@example.com --username admin --password 'ChangeMe123!'
```

The requested initial category set contains 11 categories: Technology, Education, Jobs & Career, Travel, Local Help, Housing, Shopping, Transportation, Finance, Daily Life and Other. fileciteturn4file0L74-L79

## Product flow
1. Visitor lands on the community feed.
2. Visitor registers or signs in.
3. Member creates a help request with category, urgency, type and location.
4. Other members open the request and post answers.
5. Helpful votes and best-answer actions feed the reputation loop.
6. Request owners can move requests through the intended lifecycle and solve/close them.
7. Notifications and private conversations keep people connected.
8. Reports, blocks and admin controls provide moderation and safety tooling.

## Frontend routes
- `/` — premium responsive community feed
- `/login` — sign in
- `/register` — account creation
- `/requests/new` — create a request
- `/requests/:id` — request detail + answers
- `/messages` — conversations
- `/notifications` — notifications
- `/profile/:username` — public profile

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

The API follows the requested success envelope and pagination conventions. fileciteturn4file0L107-L116

## Vercel deployment
The root `vercel.json` builds `frontend` and exposes the FastAPI app through `api/index.py`. React routes fall back to `index.html`, while `/api/*` and `/health/*` are sent to FastAPI.

Configure these Vercel environment variables before production deployment:
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM` (normally `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `CORS_ORIGINS` (only required for additional external frontend origins)
- `ENVIRONMENT=production`

Use a managed PostgreSQL provider for production. Do not commit `.env` or secrets.

## Security
Passwords are bcrypt-hashed; refresh tokens are stored as SHA-256 hashes; access/refresh JWTs rotate; protected routes enforce account status; and admin endpoints enforce the admin role. fileciteturn4file0L92-L103

## Tests
```bash
cd backend
pytest -v --cov=app --cov-report=term-missing
```

## Specification note
The supplied specification describes a larger multi-batch implementation with dedicated route/service/model files, Alembic migrations and a broad integration test suite. fileciteturn4file0L45-L56 This repository keeps the working application and deployment path explicit rather than claiming unimplemented pieces are complete.
