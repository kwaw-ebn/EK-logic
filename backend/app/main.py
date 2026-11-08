import secrets
import logging
import time
from collections import defaultdict, deque
from fastapi import FastAPI, Depends, Request, Response, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession
from . import config
from .db import get_db
from .models import User, Organization, Workspace, Session, Dataset, Analysis
from .security import current_user, owned, audit, digest, password_hash, verify_password
from .schemas import Credentials, Registration, Named, AnalysisInput, MeaningsInput
from .storage import Storage
from .analytics import read_frame, profile_frame, aggregate, report_bytes

class RedactQuery(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            args = list(record.args)
            if isinstance(args[2], str):
                args[2] = args[2].split('?')[0]
            record.args = tuple(args)
        return True

logging.getLogger('uvicorn.access').addFilter(RedactQuery())

app = FastAPI(title='EK-Logic API', version='0.1.0')
# Single-process MVP limiter; replace with shared Redis before horizontal scaling.
buckets = defaultdict(deque)

@app.middleware('http')
async def security_headers(request: Request, call_next):
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        origin = request.headers.get('origin')
        if (origin and origin != config.FRONTEND_URL) or request.headers.get('x-ek-request') != '1':
            return JSONResponse({'detail': 'Request origin could not be verified'}, status_code=403)
    if request.url.path in {'/auth/login', '/auth/register'}:
        now = time.monotonic()
        key = request.client.host if request.client else 'unknown'
        bucket = buckets[key]
        while bucket and bucket[0] < now - 60:
            bucket.popleft()
        if len(bucket) >= 20:
            return JSONResponse({'detail': 'Too many attempts; try again in a minute'}, status_code=429)
        bucket.append(now)
        if len(buckets) > 10000:
            for k in list(buckets):
                if not buckets[k] or buckets[k][-1] < now - 60:
                    buckets.pop(k, None)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response

@app.get('/health')
def health(db: DBSession = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok'}

def public_user(user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'organization_id': user.organization_id}

def start_session(db, user, response):
    token = secrets.token_urlsafe(48)
    db.add(Session(token_hash=digest(token), user_id=user.id, expires=time.time() + 86400))
    db.commit()
    response.set_cookie('ek_session', token, max_age=86400, httponly=True,
                        secure=config.PRODUCTION, samesite='lax', path='/')

@app.post('/auth/register', status_code=201)
def register(payload: Registration, response: Response, db: DBSession = Depends(get_db)):
    org = Organization(name=payload.organization.strip())
    db.add(org)
    db.flush()
    user = User(email=payload.email, name=payload.name.strip(), password_hash=password_hash(payload.password), organization_id=org.id)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Unable to register with this email')
    workspace = Workspace(name='My first workspace', organization_id=org.id)
    db.add(workspace)
    db.flush()
    audit(db, user, 'account.register', user.id)
    start_session(db, user, response)
    return public_user(user)

@app.post('/auth/login')
def login(payload: Credentials, response: Response, db: DBSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    # Equal work for unknown accounts reduces user enumeration via response time.
    stored = user.password_hash if user else '0' * 32 + ':' + '0' * 64
    valid = verify_password(payload.password, stored)
    if not user or not valid:
        raise HTTPException(401, 'Invalid email or password')
    audit(db, user, 'account.login', user.id)
    start_session(db, user, response)
    return public_user(user)

@app.post('/auth/logout', status_code=204)
def logout(request: Request, response: Response, user=Depends(current_user), db: DBSession = Depends(get_db)):
    session = db.get(Session, digest(request.cookies.get('ek_session', '')))
    db.delete(session)
    db.commit()
    response.delete_cookie('ek_session', path='/')

@app.get('/auth/me')
def me(user=Depends(current_user)):
    return public_user(user)

@app.get('/workspaces')
def workspaces(user=Depends(current_user), db: DBSession = Depends(get_db)):
    return [{'id': x.id, 'name': x.name} for x in db.scalars(select(Workspace).where(Workspace.organization_id == user.organization_id))]

@app.post('/workspaces', status_code=201)
def create_workspace(payload: Named, user=Depends(current_user), db: DBSession = Depends(get_db)):
    workspace = Workspace(name=payload.name, organization_id=user.organization_id)
    db.add(workspace)
    db.flush()
    audit(db, user, 'workspace.create', workspace.id)
    db.commit()
    return {'id': workspace.id, 'name': workspace.name}

def dataset_view(item):
    return {'id': item.id, 'name': item.name, 'created': item.created, 'profile': item.profile, 'meanings': item.meanings}

@app.get('/workspaces/{workspace_id}/datasets')
def datasets(workspace_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    owned(db, Workspace, workspace_id, user)
    return [dataset_view(x) for x in db.scalars(select(Dataset).where(Dataset.workspace_id == workspace_id).order_by(Dataset.created.desc()))]

@app.post('/workspaces/{workspace_id}/datasets', status_code=201)
async def upload(workspace_id: str, file: UploadFile = File(...), sheet: str | None = Form(None),
                 user=Depends(current_user), db: DBSession = Depends(get_db)):
    owned(db, Workspace, workspace_id, user)
    raw = await file.read(config.MAX_UPLOAD + 1)
    await file.close()
    if len(raw) > config.MAX_UPLOAD:
        raise HTTPException(413, 'Maximum file size is 10 MB')
    name = (file.filename or '').replace('\\', '/').split('/')[-1][:255]
    frame, sheets, selected = read_frame(raw, name, sheet)
    key = secrets.token_hex(24)
    profile = profile_frame(frame, sheets, selected)
    item = Dataset(workspace_id=workspace_id, organization_id=user.organization_id, name=name,
                   storage_key=key, sheet=selected, profile=profile,
                   meanings={c['name']: c['suggested_role'] for c in profile['columns']})
    storage = Storage()
    storage.put(key, raw)
    try:
        db.add(item)
        db.flush()
        audit(db, user, 'dataset.upload', item.id)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return dataset_view(item)

@app.get('/datasets/{dataset_id}')
def get_dataset(dataset_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return dataset_view(owned(db, Dataset, dataset_id, user))

@app.put('/datasets/{dataset_id}/meanings')
def update_meanings(dataset_id: str, payload: MeaningsInput, user=Depends(current_user), db: DBSession = Depends(get_db)):
    item = owned(db, Dataset, dataset_id, user)
    columns = {c['name'] for c in item.profile['columns']}
    if set(payload.meanings) != columns or not set(payload.meanings.values()) <= {'dimension', 'measure', 'date', 'ignore'}:
        raise HTTPException(422, 'Map each column to dimension, measure, date or ignore')
    item.meanings = payload.meanings
    audit(db, user, 'dataset.map', item.id)
    db.commit()
    return dataset_view(item)

def run_analysis(item, dimension, measure, operation):
    if item.meanings.get(dimension) not in {'dimension', 'date'}:
        raise HTTPException(422, 'Confirm a dimension or date role for the grouping column')
    if operation != 'count' and item.meanings.get(measure) != 'measure':
        raise HTTPException(422, 'Confirm a measure role for the numeric column')
    frame, _, _ = read_frame(Storage().get(item.storage_key), item.name, item.sheet)
    return aggregate(frame, dimension, measure, operation)

@app.get('/datasets/{dataset_id}/chart')
def chart(dataset_id: str, dimension: str, measure: str | None = None, operation: str = 'sum',
          user=Depends(current_user), db: DBSession = Depends(get_db)):
    item = owned(db, Dataset, dataset_id, user)
    return run_analysis(item, dimension, measure, operation)

@app.post('/datasets/{dataset_id}/analyses', status_code=201)
def save_analysis(dataset_id: str, payload: AnalysisInput, user=Depends(current_user), db: DBSession = Depends(get_db)):
    item = owned(db, Dataset, dataset_id, user)
    run_analysis(item, payload.dimension, payload.measure, payload.operation)
    definition = payload.model_dump(exclude={'name'})
    result = Analysis(dataset_id=item.id, organization_id=user.organization_id, name=payload.name, definition=definition)
    db.add(result)
    db.flush()
    audit(db, user, 'analysis.save', result.id)
    db.commit()
    return {'id': result.id, 'name': result.name, 'definition': definition, 'dataset_id': item.id}

@app.get('/workspaces/{workspace_id}/analyses')
def analyses(workspace_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    owned(db, Workspace, workspace_id, user)
    query = select(Analysis).join(Dataset).where(Dataset.workspace_id == workspace_id, Analysis.organization_id == user.organization_id).order_by(Analysis.created.desc())
    return [{'id': x.id, 'name': x.name, 'definition': x.definition, 'dataset_id': x.dataset_id} for x in db.scalars(query)]

@app.get('/analyses/{analysis_id}/export')
def export(analysis_id: str, format: str = 'csv', user=Depends(current_user), db: DBSession = Depends(get_db)):
    analysis = owned(db, Analysis, analysis_id, user)
    item = owned(db, Dataset, analysis.dataset_id, user)
    result = run_analysis(item, **analysis.definition)
    content, media_type = report_bytes(result, analysis.name, item.name, format)
    audit(db, user, 'analysis.export', analysis.id)
    db.commit()
    return Response(content=content, media_type=media_type,
                    headers={'Content-Disposition': f'attachment; filename="eklogic-report.{format}"'})

from .google_routes import router as google_router
app.include_router(google_router)
