# Open issue review — 18 October 2026

Review is based on source published on `codex/cloud-deployment`, not uncommitted files or assumed hardware behavior. Already closed issues were not reopened.

## Completed

| Issue | Evidence |
| --- | --- |
| #26 — AI data collection protocol | `ai/train.py` defines generated sessions, timestamped records, quality values and labels; `ai/reports/training_report.json` records sampling cadence, feature window, label horizon and label definition. `ai/README.md` documents generated data under ignored `ai/data/`, required original session/event/timestamp fields, and separation of research and live data. `backend/docs/archive-data-storage.md` documents source schemas, capture limits, missingness, provenance and review policy. This completion is for the implemented research data protocol, not clinical approval. |
| #51 — System architecture documentation | `README.md` documents the implemented architecture, data-flow diagram, repository, API, database, setup, operation and offline replay behavior. It explicitly distinguishes measured/received timestamps, original-session ownership, deterministic alerts and optional experimental AI, and records the missing hardware firmware. `ai/README.md` and `backend/docs/archive-data-storage.md` explain the research boundaries. |

## Remain open

| Issues | Remaining acceptance criteria |
| --- | --- |
| #1 | `CONTRIBUTING` and documentation of GitHub labels/milestones are absent. |
| #3 | Complete hardware BOM, wiring assumptions and power specification are absent. |
| #4 | Backend reading/sync/alert schemas and executable payload examples exist, but the requested on-device alert-state payload contract is not defined. |
| #5–#8 | Hardware environment, wiring, readout and bring-up require recorded physical verification. Display sketches alone do not prove these criteria. |
| #9–#17 | The committed firmware contains display test sketches, not the complete organized acquisition/RTC/alerts/offline-buffer/network implementation and validation notes. Uncommitted `system_test/` was not used as completion evidence. |
| #27 | The requested populated raw/generated/processed folder convention is not implemented as specified. |
| #29 | Trend/variability/deviation extraction exists, but the reusable persisted feature table required by this issue is absent. |
| #30 | Logistic regression training and group splits exist, but the required joblib artifact and approved split strategy are not evidenced; the runtime artifact is JSON and validation is synthetic only. |
| #42 | Backend retry/deduplication support exists; actual device buffering and reconnect upload are not implemented in committed firmware. |
| #44 | No recorded sensor-to-device-to-backend-to-AI-to-dashboard hardware demo. |
| #45 | No hardware calibration checklist with sign-off criteria. |
| #48 | No frontend component-test suite. |
| #49 | Software tests pass, but the full project includes hardware and no complete controlled hardware smoke-test record is present. |
| #50 | No complete milestone acceptance checklist and issue triage/classification workflow. |
| #52 | Software setup is documented; full firmware setup and hardware operation remain incomplete. |
| #53 | Final demo script, proof-of-work and aligned presentation materials are absent. |
