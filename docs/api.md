# API overview

All paths below are FastAPI paths. The frontend exposes them through `/api`. Development API docs: `http://localhost:8000/docs`. The complete machine-readable contract is in openapi.json.

State-changing requests require `X-EK-Request: 1`. Browser requests with an Origin header must match FRONTEND_URL. After login/registration, use the returned HTTP-only session cookie. There is no bearer-token shortcut.

| Route | Purpose |
| --- | --- |
| POST /auth/register | Create user, organization, first workspace and session |
| POST /auth/login | Create session |
| POST /auth/logout | Revoke current session |
| GET /auth/me | Current user's public profile |
| GET, POST /workspaces | List or create organization workspaces |
| GET, POST /workspaces/{id}/datasets | List or upload files (multipart: file, optional sheet) |
| GET /datasets/{id} | Profile, preview, mappings |
| PUT /datasets/{id}/meanings | Set complete column-role mapping |
| GET /datasets/{id}/chart | Aggregate dimension/measure/operation |
| POST /datasets/{id}/analyses | Save validated analysis definition |
| GET /workspaces/{id}/analyses | List saved analyses |
| GET /analyses/{id}/export | Export csv, xlsx or pdf via format query parameter |
| GET /integrations/status | Google configuration availability; no credentials |
| POST /workspaces/{id}/google/{provider}/authorize | OAuth URL for gsc or ga4 |
| GET /google/callback | Session-bound, single-use OAuth callback |
| GET /workspaces/{id}/connections | List public connection metadata |
| GET /connections/{id}/properties | Fetch authorized Google property IDs |
| PUT /connections/{id}/property | Set a verified property ID |
| POST /connections/{id}/sync | Import 1–31 completed days (start/end ISO dates) |
| GET /workspaces/{id}/marketing | Date-filtered totals, daily records and jobs |
| GET /health | Database connectivity check |

Cross-tenant object IDs return 404. Unauthenticated reads return 401. Validation failures return 422, oversized files 413, origin failures 403, provider failures 502 and missing Google configuration 503. There is no arbitrary SQL endpoint or file execution endpoint.
