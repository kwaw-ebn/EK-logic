import asyncio
import time
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from sqlalchemy import select
from conftest import register
from app import google, config
from app.main import app
from app.db import SessionLocal
from app.models import Connection, Metric, SyncJob


def connect(client, workspace, provider='gsc'):
    with SessionLocal() as db:
        user = client.get('/auth/me').json()
        source = Connection(organization_id=user['organization_id'], workspace_id=workspace,
                            provider=provider, property_id='https://example.com/' if provider == 'gsc' else 'properties/123',
                            encrypted_token=google.encrypt({'access_token': 'test-token', 'expires_at': time.time() + 3600}))
        db.add(source)
        db.commit()
        return source.id

def test_gsc_and_ga4_contracts(monkeypatch):
    calls = []
    async def fake_request(method, url, token=None, **kwargs):
        calls.append((method, url, kwargs))
        if 'searchAnalytics' in url:
            return {'rows': [{'clicks': 3, 'impressions': 100, 'ctr': .03, 'position': 5}]}
        return {'rows': [{'metricValues': [{'value': '12'}, {'value': '45'}]}]}
    monkeypatch.setattr(google, 'request', fake_request)
    async def collect(provider, prop):
        return [row async for row in google.daily_rows(provider, prop, 'token', '2026-01-01', '2026-01-02')]
    rows = asyncio.run(collect('gsc', 'https://example.com/'))
    assert len(rows) == 2 and rows[0][1]['clicks'] == 3
    assert 'https%3A%2F%2Fexample.com%2F' in calls[0][1]
    assert calls[0][2]['json']['dataState'] == 'final'
    rows = asyncio.run(collect('ga4', 'properties/123'))
    assert rows[0][1] == {'sessions': 12, 'event_count': 45}
    assert calls[-1][2]['json']['metrics'][0]['name'] == 'sessions'

def test_sync_idempotency_weighting_and_isolation(client, monkeypatch):
    monkeypatch.setattr(config, 'CREDENTIAL_KEY', Fernet.generate_key().decode())
    workspace = register(client)
    connection_id = connect(client, workspace)
    async def rows(*args):
        yield '2026-01-01', {'clicks': 10, 'impressions': 100, 'ctr': .1, 'position': 2}
        yield '2026-01-02', {'clicks': 0, 'impressions': 300, 'ctr': 0, 'position': 6}
    monkeypatch.setattr(google, 'daily_rows', rows)
    for _ in range(2):
        response = client.post(f'/connections/{connection_id}/sync', json={'start': '2026-01-01', 'end': '2026-01-02'})
        assert response.status_code == 200, response.text
        assert response.json()['records'] == 2
    with SessionLocal() as db:
        assert len(db.scalars(select(Metric)).all()) == 2
    data = client.get(f'/workspaces/{workspace}/marketing?start=2026-01-01&end=2026-01-02').json()['sources'][0]
    assert data['totals']['ctr'] == .025
    assert data['totals']['position'] == 5
    assert data['totals']['clicks'] == 10
    assert 'encrypted_token' not in data
    with TestClient(app, headers={'x-ek-request': '1'}) as other:
        register(other, 'stranger@example.com')
        assert other.post(f'/connections/{connection_id}/sync', json={'start': '2026-01-01', 'end': '2026-01-02'}).status_code == 404
        assert other.get(f'/connections/{connection_id}/properties').status_code == 404

def test_failed_sync_rolls_back_data_and_records_failure(client, monkeypatch):
    monkeypatch.setattr(config, 'CREDENTIAL_KEY', Fernet.generate_key().decode())
    workspace = register(client)
    source = connect(client, workspace)
    async def failing(*args):
        yield '2026-01-01', {'clicks': 1, 'impressions': 10, 'ctr': .1, 'position': 2}
        raise RuntimeError('sensitive token should not leak')
    monkeypatch.setattr(google, 'daily_rows', failing)
    response = client.post(f'/connections/{source}/sync', json={'start': '2026-01-01', 'end': '2026-01-02'})
    assert response.status_code == 502
    assert 'sensitive' not in response.text
    with SessionLocal() as db:
        assert db.scalar(select(Metric)) is None
        job = db.scalar(select(SyncJob))
        assert job.status == 'failed' and job.records == 0

def test_oauth_state_cannot_be_forged(client):
    register(client)
    assert client.get('/google/callback?state=forged&code=bad', follow_redirects=False).status_code == 400

def test_token_encryption_and_refresh(monkeypatch):
    monkeypatch.setattr(config, 'CREDENTIAL_KEY', Fernet.generate_key().decode())
    encrypted = google.encrypt({'refresh_token': 'secret', 'expires_at': 0})
    assert 'secret' not in encrypted
    assert google.decrypt(encrypted)['refresh_token'] == 'secret'
    source = Connection(encrypted_token=encrypted)
    async def fake_request(*args, **kwargs):
        assert kwargs['data']['refresh_token'] == 'secret'
        return {'access_token': 'new', 'expires_in': 3600}
    monkeypatch.setattr(google, 'request', fake_request)
    assert asyncio.run(google.access_token(source)) == 'new'
    assert google.decrypt(source.encrypted_token)['refresh_token'] == 'secret'
