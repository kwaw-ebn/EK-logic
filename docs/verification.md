# Verification record — 8 November 2026

## Executed in the development environment

- 15 Python tests passed against isolated SQLite databases. Coverage includes registration/login/logout, CSV profiling and aggregation, Excel worksheet selection, saved analyses, CSV/XLSX/PDF output, CSRF checks, malformed and oversized files, formula injection protection, cross-tenant reads/writes/exports, Google connector request contracts, encrypted refresh tokens, idempotent imports, weighted GSC metrics, failed-job rollback and OAuth state rejection and OAuth query redaction in access logs.
- Alembic upgrade/check/downgrade/upgrade round trip passed. `alembic check` reports no schema drift.
- Next.js production build and TypeScript validation passed, including the dynamic same-origin API proxy.
- Google tests used mock HTTP/provider responses. No Google account was connected and no live metrics were imported.

One warning comes from the installed Starlette TestClient's HTTPX deprecation notice. It did not fail the tests.

## Verification limits

- The managed browser preview could not reach the separately running API process. The complete browser journey was not verified locally. A Playwright test for register → upload → profile → chart → save → export is included in GitHub Actions.
- The initial GitHub Actions PostgreSQL job passed migrations, schema-drift checks and all 15 backend tests. The frontend production build also passed remotely. The browser test reached registration and upload, then exposed imprecise chart-control labels; these labels were corrected and CI was rerun. See the latest Actions result for the browser test outcome.
- Docker is unavailable in the authoring environment. Container builds/Compose startup and live Neon/Render deployment were not executed.
- Render's current Blueprint and environment-variable references were read. JSON Schema validation is recorded below; Render CLI platform validation and live deployment have not been run.
- This is an initial working vertical slice, not completion of every Phase 1 requirement. Remaining features and production-hardening work are listed in README.md and architecture.md.

## Provider configuration validation

The Render Blueprint passes the published Render JSON Schema. Render CLI platform validation was not run because the CLI is unavailable. Remote CI results, when available, are reported in the handoff.
