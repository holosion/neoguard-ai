# NeoGuard AI prototype

The saved warning model is trained and evaluated on simulated monitoring sessions. It estimates a simulated low-temperature or low-oxygen event occurring now or within 120 seconds. Its scores are experimental and have no clinical validation.

## Saved results

- `artifacts/risk_model.json`: JSON model consumed by the backend.
- `reports/training_report.json`: held-out metrics, event evaluation, limitations and artifact hash.
- `reports/split_manifest.json`: independent session assignments for training, validation and testing.
- `reports/archive_audit.json` and `reports/archive_baseline.json`: archive quality review and a separate exploratory source-label benchmark.

The current run uses 480 sessions, split into 288 training, 96 validation and 96 test sessions. Held-out row precision is 0.938 and recall is 0.818. Event sensitivity is 0.898, with 1.42 false warning episodes per simulated monitoring hour. These results describe the simulated scenarios only; they do not establish clinical performance.

## Reproduce from the project root

```powershell
.\.venv\Scripts\python.exe -m pip install -r ai/requirements.txt
.\.venv\Scripts\python.exe -m ai.train
.\.venv\Scripts\python.exe -m pytest -q
```

Training overwrites the generated model and reports. Change the seed for a new artifact version; the backend refuses a registered model version whose artifact hash changes in place. Synthetic records are generated under ignored `ai/data/` and must stay separate from live patient records.

## Backend integration

`AI_MODE=prototype` enables experimental scoring after successful device sync. `AI_MODE=disabled` disables model scoring. `AI_MODEL_PATH` optionally selects a model file. Deterministic threshold alerts operate independently.

To review the supplied ZIP datasets, run `python -m ai.audit_archives` from the project root, then run `python -m scripts.import_training_archives` from `backend/`. The audit writes de-identified staging files under ignored `ai/data/`; imports remain review-only rows in separate dataset tables and never create clinical patients or readings. Re-run the audit if `ai/data/` is absent.

Readings must include their original `session_id`, a stable `event_id` and a timezone-aware `measured_at`. The backend keeps buffered readings with their original assignment, including stopped sessions, subject to session timestamp validation. Historical readings do not trigger a current score.

The patient risk-score endpoint reports availability explicitly, including `prototype`, `disabled`, `model_unavailable`, `threshold_configuration_mismatch`, `unmonitored`, `insufficient_data` and `stale`. Prototype responses include the model version, feature contributions, data window and synthetic-only notice.

## Database verification

The PostgreSQL tests cover original-session ownership, alert episodes, persisted inference, inference failure isolation, cross-device constraints and separate archive imports. Set `NEOGUARD_TEST_DATABASE_URL` to a dedicated test database before running pytest. Each test creates and removes its own schema. Without this setting, six database tests are skipped.

The ESP32-S3 hardware integration is now connected to the hosted backend and web
app, with actual bench readings confirmed on 24 October 2026. Its OLED-style
ST7789 display uses a 10-second HR average refreshed every three seconds; that
display smoothing does not change the raw upload data, signal qualification or
model inputs. Unqualified estimates are stored as poor quality and excluded from
inference. A stable-looking display alone cannot unlock the Experimental risk
score panel or establish that its measurements are accurate.
The range-indicator revision also allows a green LED for valid displayed values
inside the configured bench limits while still labelling them as estimates.
Green does not upgrade their stored quality or make them eligible for AI scoring.

## Checkpoint: 12 October 2026

The unfinished database verification is complete:

- All 21 tests pass, including the six PostgreSQL integration tests.
- All four Alembic migrations apply successfully to a fresh test database.
- Alembic reports no differences between the migrated schema and application models.
- The PostgreSQL-backed API smoke flow passes authentication, access control, quality-aware alerts, component health, session races, pagination, sync retries and clock validation.

PostgreSQL 17.11 runtime files are saved under ignored `.local/postgres/pgsql/`. The isolated cluster is `.local/pgdata`, bound to `127.0.0.1:55432`; connection settings are in ignored `.local/test-db.json`. It is stopped after verification. This database is for tests only.

To rerun the full test suite from the project root:

```powershell
& .local/postgres/pgsql/bin/pg_ctl.exe -D .local/pgdata -l .local/postgres-server.log -o '-h 127.0.0.1 -p 55432' -w start
$taskDbConfig = Get-Content .local/test-db.json | ConvertFrom-Json
$env:NEOGUARD_TEST_DATABASE_URL = 'postgresql+psycopg://neoguard_test:' + $taskDbConfig.password + '@127.0.0.1:55432/neoguard_integration'
.\.venv\Scripts\python.exe -m pytest -q
& .local/postgres/pgsql/bin/pg_ctl.exe -D .local/pgdata -m fast -w stop
```

The next development stage is dashboard integration and collection of documented, suitable training data. Hardware firmware remains deferred. The current model remains a synthetic research prototype.
