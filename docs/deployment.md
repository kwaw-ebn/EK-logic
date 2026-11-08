# Deployment and provider setup

## Local development

Follow README.md for Docker Compose or two-terminal development. Use `.env.example` only as a template. Never commit `.env`, database files, uploads, service credentials or private sample data.

`APP_ENV=production` requires PostgreSQL, an HTTPS `FRONTEND_URL`, and `S3_BUCKET`. The app fails startup if these requirements are absent. `DATABASE_URL` accepts Neon `postgresql://` URLs and converts them to the SQLAlchemy psycopg driver. Keep Neon's TLS parameters, including `sslmode=require`. Use a migration-capable Neon connection when running Alembic.

## Neon + Render

1. Create a Neon database. Save its connection URL as backend `DATABASE_URL` in Render's secret environment settings.
2. Create a private S3-compatible bucket and a service credential limited to GetObject, PutObject and DeleteObject on that bucket. Set `S3_BUCKET`, optional `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_DEFAULT_REGION` on the API. Enable provider-side encryption, appropriate retention and backups. Do not make the bucket public.
3. Review `render.yaml`. It defines two Docker web services and does not provision Neon or object storage. It deliberately omits a fixed compute plan; review the selected defaults and pricing before applying. The evaluation app has not been load tested; Pandas and XLSX parsing can need substantially more memory than the compressed upload size.
4. Validate the template with a current Render CLI: `render blueprints validate render.yaml`. A schema check is not a live deployment test.
5. Create the Blueprint from this repository. Fill all prompted values. Use your intended HTTPS frontend URL as `FRONTEND_URL` on the API, and the API's HTTPS service URL as `API_INTERNAL_URL` on the frontend. These must refer to these two services. URLs are not secrets, but database and object-storage credentials are.
6. If the generated frontend hostname was unknown during setup, update `FRONTEND_URL` to that exact origin and redeploy the API. Avoid trailing slashes. The API permits state-changing browser requests only from this configured origin.
7. API startup runs `alembic upgrade head`, then Uvicorn on `$PORT`. Use one instance for this MVP. Move migrations to a controlled release/pre-deploy step before multi-instance rollout. Frontend starts Next.js on its injected `$PORT` (Next supports `PORT`). The proxy resolves `API_INTERNAL_URL` at runtime.
8. Verify API `/health`, account registration, uploads, charting, saved reports and exports on the HTTPS frontend. Confirm logs contain no credentials. A saved environment setting is not active until the relevant deploy completes.

The frontend proxies API requests so sessions stay on the frontend domain. Cookies are HTTP-only, SameSite=Lax and Secure in production. S3 keys remain server-side. A persistent local volume is suitable for local development only; no production disk is configured by this Blueprint.

The template uses `sync: false` prompts at initial creation. Later Blueprint syncs do not replace those secret values; manage subsequent changes in Render and redeploy. This repository has not been deployed during initial implementation. The Render CLI may not be available in the authoring environment; see verification.md for the exact checks performed.

## Google Search Console and GA4

1. In your Google Cloud project, enable Search Console API, Google Analytics Data API and Google Analytics Admin API.
2. Configure the OAuth consent screen. During testing, add the intended Google accounts as test users. Public distribution may require Google's consent-screen review.
3. Create a Web Application OAuth client. Register the exact callback: `https://YOUR-FRONTEND/api/google/callback` (local: `http://localhost:3000/api/google/callback`).
4. Set backend `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, and a valid `CREDENTIAL_KEY`. Generate a Fernet key locally and paste it directly into your secret manager:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

5. Restart/redeploy the API. In Marketing Intelligence, connect Search Console or GA4, authorize the read-only scope, choose an authorized property, select dates, and synchronize. GSC final data commonly lags the most recent dates; absence of returned rows is not recorded as zero. GA4 dates use the property's reporting timezone; GSC dates use Google's reporting convention. The comparison window is the provider date, not an inferred UTC timestamp.
6. Click Load metrics to read synchronized totals. Inspect Data Pipelines for recent jobs. Select at most 31 completed days per synchronization. Larger backfills and automatic scheduling are future work.

The adapters make real network calls only with a configured account. Unit tests use mock Google responses and are not evidence of successful live authorization. OAuth state is single-use, bound to the signed-in user, and expires after ten minutes. Changing a selected property clears the old property's imported metrics in that workspace to avoid mixing sources.

Rotate client credentials through Google's console and Render secrets. Keep the Fernet key durable: replacing it without re-encrypting stored tokens makes existing connections unreadable; reconnect those sources. Token revocation/disconnection and a key-rotation migration are later work.

## Before a broader public launch

Complete the operational-hardening roadmap in architecture.md: verification/recovery email, database RLS, role and invitation controls, shared rate limiting, scanning/quarantine, retention and deletion workflows, resource quotas, separate migration/runtime DB roles, background jobs and backups. This is a concrete list of missing implementation, not a claim that the initial slice is production complete.

## References used for the provider contracts

- https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- https://developers.google.com/analytics/devguides/reporting/data/v1/basics
- https://render.com/docs/blueprint-spec
- https://render.com/docs/configure-environment-variables

## Neon Object Storage

Neon Object Storage can provide the private S3-compatible bucket used by this app. Get the branch's storage endpoint and region, create a private bucket and a branch-scoped storage credential, and configure the API's Render environment:

- `S3_BUCKET`: private bucket name.
- `S3_ENDPOINT_URL`: the branch's complete S3 endpoint.
- `AWS_DEFAULT_REGION`: the region returned by Neon's storage API.
- `AWS_ACCESS_KEY_ID`: the credential's `token_id`.
- `AWS_SECRET_ACCESS_KEY`: its `s3_secret_access_key`.

The backend explicitly uses path-style addressing and computes checksums only when required, for compatibility with S3-compatible providers. Credentials belong only on the API service. Do not place them in frontend variables or source control. See https://neon.com/docs/storage/get-started and https://neon.com/docs/storage/authentication.

## Single-service Render deployment

When workspace capacity is limited, use the repository-root `Dockerfile` with build context `.` to run the frontend and API in one Render web service. The public Next.js server listens on Render's `PORT`; FastAPI listens only on `127.0.0.1:8000`. The internal API URL is `http://127.0.0.1:8000`. Set `FRONTEND_URL` to the new service's exact HTTPS origin. Use `/api/health` as its readiness endpoint.

The Python supervisor runs migrations before startup, forwards SIGTERM to both children and exits if either child stops. PostgreSQL and private file storage remain external on Neon. No upload bytes are stored on the ephemeral Render filesystem.

A free 512 MB instance is suitable only for evaluating small datasets. Combined Node/Pandas memory usage and cold starts should be evaluated before wider use; this deployment has not been load tested. The two-service `render.yaml` is an alternative template and should not be applied to manage the manually created single service.
