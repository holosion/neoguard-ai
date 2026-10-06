# NeoGuard backend: focused design

## Project understanding

NeoGuard is an embedded neonatal monitoring prototype for low-resource clinics. An ESP32 reads heart rate and SpO2 from the MAX30102 and temperature from the selected temperature sensor, keeps time with an RTC, displays heart rate and temperature on an LCD, and raises local alerts. Because network access may be intermittent, the device must keep timestamped readings locally and upload them later. The backend is the durable record, device registry, synchronization point, alert history, dashboard API, and later home for explainable risk scoring. PostgreSQL is the system of record and FastAPI exposes it to the dashboard and devices.

The clinical value is continuous visibility between manual checks, with a practical prototype that can operate through connectivity interruptions. It is a screening and research aid, not a diagnostic or treatment system. The strongest engineering requirements are trustworthy timestamps, safe device-to-patient assignment, reliable duplicate-safe sync, clear stale-data presentation, and transparent separation of measured facts from calculated risk.

## Decisions to settle and keep consistent

- **Current stack:** FastAPI + PostgreSQL. Older Django and Flask notes describe earlier alternatives; they are not part of this backend plan.
- **LCD and RTC:** They are device capabilities. The LCD displays locally; the backend stores the underlying readings and component health. The RTC supplies measurement time, while the server records receipt/sync time so clock drift and delayed uploads can be detected.
- **Clinical and training data:** Keep live patient/device records separate from Kaggle and synthetic training datasets. Import training data into a separate training schema or files and produce versioned model artifacts. Do not place simulated patients in the live nurse dashboard or imply that synthetic labels are clinical outcomes.
- **Risk score:** Add model inference after the reliable data path exists. Until a model has been trained and validated with documented data, show “not available”; never invent a score. Rule thresholds can generate deterministic alerts, but should not be presented as a validated predictive model.
- **Thresholds:** Store configured thresholds with units, source/citation, and version/effective date. Have a qualified supervisor review the exact values and measurement method before clinical use; source names in the notes are not a substitute for validated citations.
- **Frontend states:** Loading is a client-side request state. The API returns real data, an empty result, or explicit freshness/availability metadata. Stale means the latest measurement is old, even if it synced recently; show measurement time and sync time separately.

## Database design

Use SQLAlchemy 2 models and Alembic migrations as the schema source of truth. Keep database constraints for invariants that must hold even if a second API path is added. Store timestamps as `TIMESTAMPTZ` in UTC and retain both the device measurement time and server receipt time.

### First release tables

| Table | Purpose and key relationships |
|---|---|
| `users` | Staff accounts and role; password hash only. |
| `patients` | Pseudonymous `patient_code`, birth/gestational details needed for care; avoid names and unnecessary identifiers. |
| `risk_profiles` | Clinician-entered factors, one current profile per patient, with who/when updated. |
| `devices` | Unique device code, lifecycle status, firmware/hardware versions, location and last contact. |
| `device_credentials` | Hashed per-device secret or token, revocable and separate from staff login credentials. |
| `device_components` | Installed RTC, LCD, MAX30102, temperature sensor, buzzer, LED and ESP32 component inventory. |
| `monitoring_sessions` | Time-bounded assignment of one device to one patient. Enforce at most one active session per device and per patient. |
| `readings` | Measured HR, SpO2, temperature, quality, measurement time, server receipt time, session and unique device event ID. |
| `alerts` | Threshold/device alerts tied to a session and optionally a reading; acknowledgment references a user and timestamp. |
| `device_telemetry` | Battery, RSSI, uptime and other device-level snapshots. |
| `component_health_logs` | Timestamped self-check results for registered components. |
| `thresholds` | Parameter, value, unit, source, version/effective time and enabled status. |
| `audit_log` | Actor, action, resource, time and minimal structured details for sensitive staff actions. |

### Add with the AI milestone

`risk_scores` should link to the patient and the monitoring session, and save score, category, `model_version`, feature snapshot, explanation, computation time, and the data window used. `outcome_labels` and dataset subject/import records belong in the isolated training-data area, with provenance and label source. Add them when the training pipeline is defined rather than treating generated labels as ground truth. Trend aggregates can be derived from readings first; add a cache table only if measured query performance requires it.

The provided archives have now shaped the training-data storage models too: `dataset_imports`, `dataset_import_rows`, `dataset_subjects`, and `dataset_observations` are separate from `patients`, `monitoring_sessions`, and live `readings`. See [docs/archive-data-storage.md](docs/archive-data-storage.md) for the inspected fields, quality issues, and archive-specific mapping rules.

### Important integrity rules

1. Add a partial unique index for active sessions on `device_id`, and another for active sessions on `patient_id` (if your operating model permits only one active monitor per neonate). Validate the assignment in a transaction when a session starts.
2. Give each device reading a stable `event_id` generated before local buffering. Enforce uniqueness per device so retrying an offline batch cannot duplicate readings. Keep sync requests retry-safe.
3. A reading belongs to a session. Imported research observations should use separate tables/schema rather than nullable `session_id` rows that leak into live queries.
4. Use foreign keys for acknowledgments (`acknowledged_by_user_id`) rather than usernames in text. Preserve historical rows by stopping sessions and retiring devices instead of deleting them.
5. Validate plausible ranges in Pydantic and also enforce database checks. Record rejected batch items with actionable errors without silently changing measurements.
6. Index readings by `(session_id, measured_at DESC)`, alerts by `(session_id, acknowledged, created_at DESC)`, and telemetry/component logs by `(device_id, measured_at DESC)`.

## Backend boundaries and build order

Keep route handlers thin. A request schema validates input, a service owns transaction/business rules, SQLAlchemy models represent persisted records, and response schemas define the dashboard contract. Avoid putting SQL, threshold policy, and model code directly into FastAPI endpoints.

```text
backend/app/
  main.py
  core/          settings, database, staff auth, device auth
  models/        SQLAlchemy tables
  schemas/       request and response contracts
  api/v1/        auth, patients, devices, sessions, readings, alerts, admin
  services/      sync, session assignment, threshold alerts, audit, risk scoring (later)
  migrations/    Alembic revisions
backend/scripts/ data import/export and admin bootstrap commands
```

Build in this order:

1. Define the device message contract and relational constraints; create migrations and a local PostgreSQL setup.
2. Add staff login/roles and separate device authentication. Never put database passwords, JWT secrets, Wi-Fi credentials, or a shared device secret in source control.
3. Implement patients, devices, component registration, and transactional start/stop session operations.
4. Implement offline batch sync. Authenticate device, verify it is active and assigned to an active session, validate timestamps/ranges, deduplicate by event ID, persist readings plus telemetry/component checks, update last contact, and return per-event accepted/duplicate/rejected results. Make transaction behavior explicit.
5. Implement dashboard reads: patient list with latest reading/session, reading history, alerts, device health, and admin counts. Calculate freshness from measurement time; return `last_measured_at`, `last_synced_at`, and a `data_status` such as `empty`, `fresh`, or `stale`.
6. Add threshold alert generation with a recorded threshold version and a unique/idempotency rule to avoid creating the same alert on every retry.
7. Only then add the offline model-training pipeline, model versioning, inference service, risk score persistence, and explanation display.

## Initial API contract

Prefix endpoints with `/api/v1`. Use resource IDs in routes, pagination for histories, and UTC ISO-8601 timestamps.

| Endpoint | First-release behavior |
|---|---|
| `POST /auth/login`, `GET /auth/me` | Staff token and current staff profile; registration/bootstrap restricted to an administrator command or admin role. |
| `GET/POST /patients`, `GET/PATCH /patients/{id}` | Patient list/detail and controlled patient updates. |
| `GET/POST /devices`, `GET/PATCH /devices/{id}` | Admin device registry and component configuration. |
| `POST /sessions`, `POST /sessions/{id}/stop` | Clinician/admin assignment; enforce active-session uniqueness transactionally. |
| `POST /devices/sync` | Device-authenticated, retry-safe batch of readings, telemetry and component checks. |
| `GET /patients/{id}/readings?from=&to=&limit=` | Real persisted time series with freshness metadata and threshold configuration/version. |
| `GET /alerts?patient_id=&acknowledged=` | Filtered alert history; `POST /alerts/{id}/acknowledge` records authenticated user and time. |
| `GET /devices/{id}/health` | Last seen, latest telemetry, component status and stale/offline status. |
| `GET /admin/overview` | Counts and latest timestamps computed from stored records. |
| `GET /patients/{id}/risk-score` | Later: latest persisted score/explanation, or a clear `not_available` / `insufficient_data` result. |

Return `200` with an empty collection for a valid query with no rows. The frontend owns loading UI. Return freshness metadata for readings/devices. Treat insufficient risk data as an expected availability state (for example, `200` with `status: "insufficient_data"`), not a malformed-request `400`.

## Device sync payload (proposed)

```json
{
  "device_code": "DEV-001",
  "firmware_version": "0.1.0",
  "readings": [
    {
      "event_id": "a stable UUID generated and stored by the device",
      "measured_at": "2026-10-06T09:00:00Z",
      "heart_rate_bpm": 145,
      "spo2_percent": 96,
      "temperature_c": 36.7,
      "quality": "ok"
    }
  ],
  "telemetry": {
    "reported_at": "2026-10-06T09:01:00Z",
    "battery_percent": 85,
    "wifi_rssi_dbm": -70,
    "uptime_seconds": 3600
  },
  "component_checks": [
    {"component_type": "RTC", "checked_at": "2026-10-06T09:01:00Z", "status": "ok"},
    {"component_type": "LCD", "checked_at": "2026-10-06T09:01:00Z", "status": "error", "error_code": "timeout"}
  ]
}
```

The RTC timestamp is the observation time; server receipt time is recorded independently. The device should retain unacknowledged event IDs and resend them until the API confirms receipt. The API should acknowledge individual event outcomes so one malformed reading does not cause an infinite retry of an otherwise valid batch.

## AI integration boundary

Train in `A.I/` from clearly identified, licensed/appropriate datasets and synthetic data, with subject-level separation between train and evaluation sets to prevent leakage. Track provenance, label definitions, missingness, model version, and evaluation results. Do not claim clinical validity from synthetic data alone. The backend inference service should consume a documented feature vector, return a probability plus model version and interpretable contributions, and persist an immutable prediction snapshot. Keep deterministic safety thresholds independent of the model so a missing or failed model never disables device/local alerts. A clinician must be able to distinguish measured vitals, threshold alerts, and model estimates.

## Scope for the first working backend

Prioritize staff/device authentication, PostgreSQL migrations, patient/device/session management, offline-safe sync, persisted readings, threshold alerts, acknowledgments/audit, and dashboard queries. Defer Kaggle import into production readings, synthetic patient seeding in the clinical UI, trend-summary tables, scheduled five-minute scoring, and AI-generated alerts until the underlying data and labels are trustworthy.

## Code scaffold and local setup

The current implementation is under `backend/app`. It uses synchronous SQLAlchemy sessions behind FastAPI dependencies and PostgreSQL as the supported database. No database is created automatically at application startup; Alembic owns schema changes.

From a terminal in `backend/`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d postgres
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
py -m scripts.seed_admin
uvicorn app.main:app --reload
```

Inspect the generated initial migration before applying it. Keep migration files in version control. Set a unique `JWT_SECRET_KEY` and PostgreSQL password in `.env`; do not commit `.env`. The Compose password is only for local development.

The interactive API description is available at `/docs`; liveness is `/health`. Staff login uses OAuth2 form fields (`username` accepts username or email, plus `password`). Admins create staff accounts with `POST /api/v1/auth/users`. Admin device provisioning returns its random `device_secret` once; store that value securely on the device and send it as `Authorization: Bearer <device_secret>` to `/api/v1/devices/sync`.

Sync schema validation rejects a malformed batch with HTTP 422. Valid events in an accepted request return per-event `accepted`, `duplicate`, or `rejected` results. Store each event UUID in the device's offline queue and remove it only after an accepted/duplicate acknowledgment. A transaction persists readings, generated threshold alerts, telemetry and component checks together. Threshold alert generation is rule-based and independent of the unimplemented risk model.

### Implemented routes

- Staff: `POST /auth/login`, `GET /auth/me`, admin-only `POST /auth/users`.
- Patients: list/create/detail/update, risk profile get/upsert, readings history, and an explicit not-available risk-score response.
- Devices: list/detail, admin provisioning, and device-authenticated batch sync.
- Sessions: list/start/stop with database uniqueness constraints for active patient/device assignments.
- Alerts: filter/list and acknowledge with staff identity and audit record.
- Admin: overview and device connection/telemetry summary.

This is a development scaffold, not a clinically validated or deployment-hardened medical system. The threshold defaults are configurable starting points that need an approved clinical source and review before any care use. Apply TLS, secret rotation, backups, access reviews, retention policy, and operational monitoring before deployment beyond a controlled prototype.
