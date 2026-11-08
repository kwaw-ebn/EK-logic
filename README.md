# EK-Logic

**Turn Data Into Decisions.**

A working first vertical slice of the EK-Logic analytics platform: Next.js + TypeScript, FastAPI, PostgreSQL/Neon, Pandas, and private file storage. This is an early MVP, not the completed multi-phase SaaS brief.

## Implemented

- Registration, password login, logout, expiring server-side sessions and organization isolation.
- Workspace creation and switching within an organization.
- CSV and XLSX upload, named worksheet selection, bounded parsing and original-file storage.
- Column profiling: missing cells, duplicates, inferred types, numeric statistics and source previews.
- Editable semantic roles; configurable sum, mean, count, min and max aggregation.
- Interactive bar/line charts with accessible data tables, light/dark theme and responsive layouts.
- Saved analysis definitions and CSV, Excel and PDF exports with spreadsheet formula protection.
- Real read-only Google OAuth, authorized property selection, encrypted token storage, refresh, manual daily GSC/GA4 synchronization, metric totals and job history. These need your Google credentials; live-account verification has not been performed.
- Alembic migration, OpenAPI specification, Docker Compose, Render deployment template, tests and GitHub Actions.

No sample metrics are shown as real performance. The optional `examples/public_health_demo.csv` is synthetic and labeled accordingly.

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:3000`, create your own account, and upload a spreadsheet. The Compose database credentials are explicitly development-only. Backend and database ports are not published. SQLite is also supported for local development and unit tests; production requires PostgreSQL and private S3-compatible storage.

## Run without Docker

Use Python 3.12+ and Node 24.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r backend/requirements.lock
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

In another terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. The Next.js API proxy reads `API_INTERNAL_URL` at request time, defaulting to `http://127.0.0.1:8000`. Set backend environment variables in the shell or pass `uvicorn --env-file ../.env`; Python does not load `.env` implicitly. For local non-Docker mode, override the Compose `DATABASE_URL` with SQLite or a reachable PostgreSQL URL.

## Verify

```bash
cd backend
pip install pytest
python -m pytest -q
alembic check
cd ../frontend
npm run build
npm run test:e2e
```

`test:e2e` needs Playwright Chromium installed (`npx playwright install chromium`) and a Python environment with the backend dependencies. It starts local API/frontend servers. CI uses PostgreSQL for backend checks and a separate SQLite database for browser workflow testing. Never point test jobs at production: tests reset their database.

## Documentation

- [Architecture, ER diagram and roadmap](docs/architecture.md)
- [Deployment and Google setup](docs/deployment.md)
- [User guide](docs/user-guide.md)
- [API overview](docs/api.md) and [generated OpenAPI schema](docs/openapi.json)
- [Verification record and limitations](docs/verification.md)

## Boundaries of this milestone

Email verification/reset, invitations, fine-grained roles and workspace ACLs, PostgreSQL RLS, malware scanning, cleaning transformations, automatic sync scheduling, query-level SEO opportunities, GA4 acquisition breakdowns, lead mappings, Windsor.ai, GBP, AI, forecasting, and billing are not implemented. The app does not claim these capabilities.

The current login limiter is process-local and, behind the Next.js proxy, applies to the proxy address rather than individual users. Deploy one API instance for evaluation; use a trusted-edge/shared limiter before a public launch. Synchronization is synchronous and intended for small manual 1–31-day batches. Requests for one source should run sequentially. Metrics do not include missing days as zeros. GA4 event counts are not leads. GSC average position is not live rank.

Production deployment and Google live-data verification require your service configuration. No deployment, paid service creation, or credentials are included in this repository.
