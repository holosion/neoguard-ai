# Local run

The repo uses one React frontend (`Frontend/`), one FastAPI backend (`backend/`), and PostgreSQL. AI scoring and device firmware remain separate follow-up work.

## Prerequisites

- Python environment at `backend/.venv` with `backend/requirements-dev.txt` installed
- Node.js and frontend packages installed with `npm ci` in `Frontend/`
- PostgreSQL on the port configured in ignored `backend/.env` (the example uses `5432`); or the bundled local PostgreSQL runtime and data directory under ignored `.local/`
- Database schema applied with `alembic upgrade head` from `backend/`

Copy `backend/.env.example` to `backend/.env`, set a unique `JWT_SECRET_KEY`, and set `DATABASE_URL` for the local PostgreSQL instance. Do not commit `.env` files.

Apply the database schema once with `alembic upgrade head` from `backend/`. Then start the whole local project from the backend directory:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

During development, FastAPI checks the configured database connection. If a local database is stopped, it starts the sole installed PostgreSQL Windows service when one is present, or the bundled runtime when available. It also starts the Vite frontend if it is not already running. Stop the backend with `Ctrl+C`; it stops the frontend process it started. PostgreSQL remains running.

The equivalent `./start-local.ps1` launcher is still available from the repository root.

- Frontend: http://127.0.0.1:5173
- API docs: http://127.0.0.1:8000/docs
- Backend API prefix: `/api/v1`

For a separately hosted frontend, set `VITE_API_BASE_URL` and configure backend `CORS_ORIGINS` with the frontend origin.
