import hashlib
import hmac
import secrets
import time
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession
from .db import get_db
from .models import Session, User, AuditEvent

def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()

def password_hash(value: str):
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), 600000).hex()
    return f'{salt}:{key}'

def verify_password(value: str, stored: str):
    salt, expected = stored.split(':')
    actual = hashlib.pbkdf2_hmac('sha256', value.encode(), salt.encode(), 600000).hex()
    return hmac.compare_digest(actual, expected)

def current_user(request: Request, db: DBSession = Depends(get_db)):
    token = request.cookies.get('ek_session', '')
    session = db.get(Session, digest(token))
    if not session or session.expires < time.time():
        raise HTTPException(401, 'Please sign in')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, 'Please sign in')
    return user

def owned(db, model, object_id, user):
    obj = db.get(model, object_id)
    if not obj or obj.organization_id != user.organization_id:
        raise HTTPException(404, 'Resource not found')
    return obj

def audit(db, user, action, resource_id):
    db.add(AuditEvent(organization_id=user.organization_id, user_id=user.id,
                      action=action, resource_id=resource_id))
