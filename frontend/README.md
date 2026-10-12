# NeoGuard frontend

This is the single web frontend for the project. It serves the ward overview, patient and session management, alerts, device monitoring, staff access, clinic setup, and server settings from the FastAPI API. The application has no sample-data or mock mode.

## Run locally

1. Install dependencies with `npm ci`.
2. Copy `.env.example` to `.env` if you need a non-default API URL.
3. Start the backend from `../backend` with `uvicorn app.main:app --reload`.
4. Start this app with `npm run dev`.

Vite serves on port 5173 and proxies `/api/v1` to `http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` to the backend URL for a separately hosted frontend and add its origin to the backend `CORS_ORIGINS`.

## Application areas

- Ward overview and live patient triage
- Patient records, monitoring sessions, history, alerts, and CSV export
- Device registry, health details, and telemetry history
- Admin overview, staff access, clinic setup, and server threshold configuration

The AI scoring area and device firmware remain separate follow-up work. Threshold values shown by the app come from the backend API.
