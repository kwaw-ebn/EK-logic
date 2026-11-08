import secrets
import time
from datetime import date
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from . import config, google
from .db import get_db
from .models import Workspace, Connection, Metric, SyncJob, OAuthState
from .security import current_user, owned, audit, digest
from .schemas import PropertyInput, SyncInput

router = APIRouter()

def view(c):
    return {'id': c.id, 'provider': c.provider, 'property_id': c.property_id, 'last_sync': c.last_sync}

@router.get('/integrations/status')
def status(user=Depends(current_user)):
    return {'google_configured': google.configured()}

@router.get('/workspaces/{workspace_id}/connections')
def connections(workspace_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    owned(db, Workspace, workspace_id, user)
    return [view(x) for x in db.scalars(select(Connection).where(Connection.workspace_id == workspace_id))]

@router.post('/workspaces/{workspace_id}/google/{provider}/authorize')
def authorize(workspace_id: str, provider: str, user=Depends(current_user), db: Session = Depends(get_db)):
    owned(db, Workspace, workspace_id, user)
    if provider not in google.SCOPES:
        raise HTTPException(422, 'Choose gsc or ga4')
    if not google.configured():
        raise HTTPException(503, 'Configure Google OAuth and encryption before connecting')
    state = secrets.token_urlsafe(40)
    db.add(OAuthState(token_hash=digest(state), user_id=user.id, workspace_id=workspace_id,
                      provider=provider, expires=time.time() + 600))
    db.commit()
    params = {'client_id': config.GOOGLE_CLIENT_ID, 'redirect_uri': config.GOOGLE_REDIRECT_URI,
              'response_type': 'code', 'scope': google.SCOPES[provider], 'state': state,
              'access_type': 'offline', 'prompt': 'consent'}
    return {'url': 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode(params)}

@router.get('/google/callback')
async def callback(state: str, code: str | None = None, error: str | None = None,
                   user=Depends(current_user), db: Session = Depends(get_db)):
    item = db.get(OAuthState, digest(state))
    if not item or item.user_id != user.id or item.expires < time.time():
        raise HTTPException(400, 'Invalid or expired OAuth request')
    owned(db, Workspace, item.workspace_id, user)
    workspace_id, provider = item.workspace_id, item.provider
    db.delete(item)
    db.commit()
    if error or not code:
        return RedirectResponse(config.FRONTEND_URL + '/?connection=cancelled', status_code=303)
    tokens = await google.request('POST', 'https://oauth2.googleapis.com/token', data={
        'client_id': config.GOOGLE_CLIENT_ID, 'client_secret': config.GOOGLE_CLIENT_SECRET,
        'redirect_uri': config.GOOGLE_REDIRECT_URI, 'grant_type': 'authorization_code', 'code': code})
    if google.SCOPES[provider] not in tokens.get('scope', '').split():
        raise HTTPException(400, 'Required read-only Google scope was not granted')
    tokens['expires_at'] = time.time() + tokens.get('expires_in', 3600)
    connection = db.scalar(select(Connection).where(Connection.workspace_id == workspace_id, Connection.provider == provider))
    if connection:
        connection.encrypted_token = google.encrypt(tokens)
    else:
        connection = Connection(organization_id=user.organization_id, workspace_id=workspace_id,
                                provider=provider, encrypted_token=google.encrypt(tokens))
        db.add(connection)
    db.flush()
    audit(db, user, 'google.connect', connection.id)
    db.commit()
    return RedirectResponse(config.FRONTEND_URL + '/?connection=success', status_code=303)

@router.get('/connections/{connection_id}/properties')
async def properties(connection_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    connection = owned(db, Connection, connection_id, user)
    token = await google.access_token(connection)
    result = await google.properties(connection.provider, token)
    db.commit()
    return result

@router.put('/connections/{connection_id}/property')
async def select_property(connection_id: str, payload: PropertyInput, user=Depends(current_user), db: Session = Depends(get_db)):
    connection = owned(db, Connection, connection_id, user)
    available = await google.properties(connection.provider, await google.access_token(connection))
    if payload.property_id not in {p['id'] for p in available}:
        raise HTTPException(403, 'This Google account does not authorize the selected property')
    if connection.property_id != payload.property_id:
        db.execute(delete(Metric).where(Metric.connection_id == connection.id))
        connection.last_sync = None
    connection.property_id = payload.property_id
    audit(db, user, 'google.property', connection.id)
    db.commit()
    return view(connection)

@router.post('/connections/{connection_id}/sync')
async def sync(connection_id: str, payload: SyncInput, user=Depends(current_user), db: Session = Depends(get_db)):
    connection = owned(db, Connection, connection_id, user)
    if not connection.property_id:
        raise HTTPException(422, 'Select a property first')
    job = SyncJob(connection_id=connection.id)
    db.add(job)
    db.commit()
    try:
        token = await google.access_token(connection)
        async for day, values in google.daily_rows(connection.provider, connection.property_id, token, payload.start, payload.end):
            row = db.scalar(select(Metric).where(Metric.connection_id == connection.id, Metric.day == day))
            if row:
                row.values = values
            else:
                db.add(Metric(connection_id=connection.id, day=day, values=values))
            job.records += 1
        connection.last_sync = time.time()
        job.status = 'success'
        audit(db, user, 'google.sync', connection.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(SyncJob, job.id)
        job.status, job.error, job.records = 'failed', 'Synchronization failed; verify permissions and date range', 0
        db.commit()
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(502, 'Synchronization failed; retry later') from exc
    return {'id': job.id, 'status': job.status, 'records': job.records}

@router.get('/workspaces/{workspace_id}/marketing')
def marketing(workspace_id: str, start: str, end: str, user=Depends(current_user), db: Session = Depends(get_db)):
    owned(db, Workspace, workspace_id, user)
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if last < first:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, 'Choose a valid date range')
    output = []
    for connection in db.scalars(select(Connection).where(Connection.workspace_id == workspace_id)):
        metrics = db.scalars(select(Metric).where(Metric.connection_id == connection.id, Metric.day >= start, Metric.day <= end).order_by(Metric.day)).all()
        totals = {}
        if metrics and connection.provider == 'gsc':
            clicks = sum(m.values['clicks'] for m in metrics)
            impressions = sum(m.values['impressions'] for m in metrics)
            totals = {'clicks': clicks, 'impressions': impressions,
                      'ctr': clicks / impressions if impressions else None,
                      'position': sum(m.values['position'] * m.values['impressions'] for m in metrics) / impressions if impressions else None}
        elif metrics:
            totals = {k: sum(m.values[k] for m in metrics) for k in ['sessions', 'event_count']}
        jobs = db.scalars(select(SyncJob).where(SyncJob.connection_id == connection.id).order_by(SyncJob.created.desc()).limit(10))
        output.append({**view(connection), 'totals': totals,
                       'daily': [{'day': m.day, **m.values} for m in metrics],
                       'jobs': [{'id': j.id, 'status': j.status, 'records': j.records, 'error': j.error, 'created': j.created} for j in jobs]})
    return {'sources': output, 'limitations': ['Missing days are not assumed to be zero.',
             'GSC average position is not a live rank. Recent final data may be unavailable.',
             'GA4 event counts are not verified leads. Historical data is limited to explicitly synchronized days.']}
