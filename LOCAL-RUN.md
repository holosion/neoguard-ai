# Local run

The repo uses one React frontend (`Frontend/`), one FastAPI backend (`backend/`), and PostgreSQL. AI scoring and device firmware remain separate follow-up work.

## Prerequisites

- Python environment at `backend/.venv` with `backend/requirements-dev.txt` installed
- Node.js and frontend packages installed with `npm ci` in `Frontend/`
- PostgreSQL on `127.0.0.1:55432`, configured in ignored `backend/.env`; or the bundled local PostgreSQL runtime and data directory under ignored `.local/`
- Database schema applied with `alembic upgrade head` from `backend/`

Copy `backend/.env.example` to `backend/.env`, set a unique `JWT_SECRET_KEY`, and set `DATABASE_URL` for the local PostgreSQL instance. Do not commit `.env` files.

Run `./start-local.ps1` from the repository root. It starts PostgreSQL when the bundled runtime exists, starts FastAPI and Vite in the background, then checks HTTP readiness.

- Frontend: http://127.0.0.1:5173
- API docs: http://127.0.0.1:8000/docs
- Backend API prefix: `/api/v1`

For a separately hosted frontend, set `VITE_API_BASE_URL` and configure backend `CORS_ORIGINS` with the frontend origin.
