# Run locally

Run `./start-local.ps1` from the repository root. It starts PostgreSQL, FastAPI, and the connected frontend in background processes and checks HTTP readiness.

- Frontend: http://127.0.0.1:5173
- API docs: http://127.0.0.1:8000/docs
- PostgreSQL: `127.0.0.1:55432`, database `neoguard`.
- Login: `admin`; password is `BOOTSTRAP_ADMIN_PASSWORD` in `backend/.env`.
- Logs: `.local/backend.*.log`, `.local/frontend.*.log`, `.local/postgres-server.log`.

Secrets are in ignored `.env` files. Mock mode is disabled. Vite proxies `/api/v1` to the backend on port 8000. For a separately hosted production frontend, configure `VITE_API_BASE_URL` and backend CORS origins.

Dependencies are installed in `.venv` and `frontend/node_modules`; database migrations are applied. The existing integration database is separate. To repeat API/database verification, run `../.venv/Scripts/python.exe -m scripts.smoke_test_live` from `backend/`; it cleans up its temporary records.

`neonatal-dashboard/` is a separate visual prototype. The backend-connected application is `frontend/`.
