# Cloud deployment

Deployed on 18 October 2026 from `codex/cloud-deployment` (application commit `fb6037f`). This branch includes the three local application commits that were ahead of `main`. Existing uncommitted dashboard-preview and hardware changes were excluded.

| Component | Location |
| --- | --- |
| Frontend | https://neoguard-ai-lovat.vercel.app |
| Backend | https://neoguard-api-wwth.onrender.com |
| Backend health | https://neoguard-api-wwth.onrender.com/health |
| Vercel project | `neoguard-ai` / `prj_SpUEEryGJq08IVNvAb8bCpDLUCob` |
| Render service | `neoguard-api` / `srv-dbaggf67bikc73ei03j0`, My Workspace |
| Neon project | `neoguard-ai` / `mute-darkness-75292999` |
| Database | PostgreSQL 17, `neoguard`, `production` branch, AWS Ohio |

The frontend uses Vercel's Vite preset, root directory `frontend`, `npm ci`, `npm run build`, and output directory `dist`. `VITE_API_BASE_URL` points to the Render backend's `/api/v1` endpoint. `frontend/vercel.json` supports direct navigation to React routes.

Render uses Python 3.12.10 on the free plan in Ohio. The build command is `pip install -r backend/requirements.txt`. The start command is:

```sh
cd backend && python -m alembic upgrade head && python -m scripts.seed_admin && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
```

The free plan runs migrations before startup because a separate pre-deploy command is unavailable on that plan. Migration failure prevents startup. The seed command creates the initial administrator and provisional thresholds only when that account does not exist. Secrets are configured in Render, not committed. `APP_ENV=production` disables API documentation and local development service startup. CORS permits the project's two stable Vercel origins. AI scoring remains the existing synthetic research prototype.

The initial admin username is `admin`. Its randomly generated password is in the ignored local file `.local/neoguard-deployment-credentials.json`, restricted to the current Windows user. Do not commit that file. No patient data was imported or copied from local databases.

## Updating

The services were created through the connected provider tools. Render follows `codex/cloud-deployment`; pushing that branch triggers a backend deploy. Vercel is connected to the GitHub repository, whose default branch remains `main`; this production release was explicitly deployed from `codex/cloud-deployment`. Until the deployment branch is merged, future frontend production releases should explicitly select the same branch. A merge to `main` does not automatically change Render's selected branch.

For a repeat release, verify the branch and commit on both providers, wait for Vercel `READY` and Render `live`, then repeat the checks below. Database upgrades use the checked-in Alembic history; do not replace them with ORM table creation.

## Verification

- Frontend production build succeeds; `/login` and direct `/admin/dashboard` navigation return HTML.
- All 22 automated tests pass, including all six isolated PostgreSQL integration tests.
- Backend `/health` returns 200.
- Production administrator login, `/auth/me`, and the database-backed `/admin/overview` return 200.
- Browser preflight from the deployed frontend returns its explicit allowed origin.
- Unauthenticated admin overview returns 401; production `/docs` returns 404.
- Neon migrations applied successfully and the initial admin was created.

Render's free service may sleep while idle. This remains the documented research prototype; hardware acquisition, offline local alerts, and clinical validation are not established by deployment.
