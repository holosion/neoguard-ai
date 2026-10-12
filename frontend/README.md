# Neonatal Monitor front end (connected to the NeoGuard backend)

React 18 + Vite, React Router, Zustand, Axios, Tailwind, React Hook Form + Zod, Recharts, Lucide.

## Run
    npm install
    npm run dev

## Connecting to the NeoGuard backend
Copy `.env.example` to `.env`; mock mode is off and the API path is `/api/v1`. Vite proxies API requests to `http://127.0.0.1:8000`, and serves the frontend at `http://127.0.0.1:5173` with a fixed port. Start the backend first (`uvicorn app.main:app --reload` in `backend/`), then `npm run dev`, or use `../start-local.ps1` for the configured local stack.
For a separately hosted frontend, set `VITE_API_BASE_URL` to the backend URL and add the frontend origin to backend `CORS_ORIGINS`.
All response mapping is in `src/api/backend.js`.

Works with the backend as it is today: sign in, patient list, patient detail, readings, experimental risk score, alerts and acknowledgement, devices (register with one-time secret, edit, retire), device health, start session, create staff account.

Needs backend changes (the pages show a clear message until then):
- Staff self-registration and approval: `POST /auth/request-access`, `GET /auth/users`, `PATCH /auth/users/{id}`.
- Starting a session late: the backend starts sessions at the current time, and a device cannot sync readings without a session ID.
- Device storage use and battery/WiFi history: the backend stores only the latest telemetry and has no storage field.
- `GET /patients/{id}` returns no session or device, so the detail page reads the patient list.
- Alert thresholds are not readable through the API, so the chart bands use the same defaults as the server.

## Pages
Nurse and clinical officer: Triage (with a Needs attention panel), Patients (search, register, start and end sessions for roles allowed to), Patient detail, Alerts, Devices (read-only), Profile.
Admin: Overview, Devices, Device detail, Patients, Sessions, Alerts, Users, Settings (read-only thresholds).
Who may register patients and start or end sessions is one list, `SESSION_MANAGER_ROLES` in `src/utils/constants.js`.

## Mock mode
Set `VITE_USE_MOCK=true` in `.env` to run on sample data without a backend.
Sign in with any password. A username starting with `admin` opens the admin dashboard; anything else opens the nurse dashboard.
To use your backend, set `VITE_USE_MOCK=false` and `VITE_API_BASE_URL`.

## Done in stage 3
Admin dashboard: Overview (tiles, needs-attention list, device health, critical alerts), Devices (register, edit, assign with back-dated start, decommission), Device detail (component health, battery and WiFi charts), Users (approve or reject staff, disable accounts), and the Request access page.

## Done in stage 2
Patient detail (vitals with trends, Recharts trend chart with threshold bands and alert markers, risk score, alerts timeline, CSV export, stale and sync notices) and the global Alerts inbox with acknowledge.

## Done in stage 1
Sign in, role-based routing, sidebar layout, Triage page (summary filters, sorting, stale rows, loading, empty and error states).
Other pages are placeholders and are built in later stages.
