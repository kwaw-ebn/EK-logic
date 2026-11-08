# Single Render service: Next.js is public; FastAPI listens on loopback only.
FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim-bookworm AS python-deps
WORKDIR /build
COPY backend/requirements.lock ./
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.lock

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home app
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY --from=python-deps /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app backend/ ./backend/
COPY --from=frontend --chown=app:app /build/ ./frontend/
COPY --chown=app:app deploy/ ./deploy/
RUN mkdir -p /app/data && chown app:app /app/data
ENV PATH=/opt/venv/bin:$PATH \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    API_INTERNAL_URL=http://127.0.0.1:8000 \
    PORT=10000
USER app
EXPOSE 10000
CMD ["python", "/app/deploy/run.py"]
