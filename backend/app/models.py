import time
import uuid
from sqlalchemy import String, Text, ForeignKey, JSON, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid():
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = 'organizations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(120))

class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    expires: Mapped[float] = mapped_column(Float)

class Workspace(Base):
    __tablename__ = 'workspaces'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))

class Dataset(Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    sheet: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profile: Mapped[dict] = mapped_column(JSON)
    meanings: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[float] = mapped_column(Float, default=time.time)

class Analysis(Base):
    __tablename__ = 'analyses'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    definition: Mapped[dict] = mapped_column(JSON)
    created: Mapped[float] = mapped_column(Float, default=time.time)

class Connection(Base):
    __tablename__ = 'connections'
    __table_args__ = (UniqueConstraint('workspace_id', 'provider'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    provider: Mapped[str] = mapped_column(String(10))
    encrypted_token: Mapped[str] = mapped_column(Text)
    property_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_sync: Mapped[float | None] = mapped_column(Float, nullable=True)

class OAuthState(Base):
    __tablename__ = 'oauth_states'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    provider: Mapped[str] = mapped_column(String(10))
    expires: Mapped[float] = mapped_column(Float)

class Metric(Base):
    __tablename__ = 'metrics'
    __table_args__ = (UniqueConstraint('connection_id', 'day'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    connection_id: Mapped[str] = mapped_column(ForeignKey('connections.id'), index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    values: Mapped[dict] = mapped_column(JSON)

class SyncJob(Base):
    __tablename__ = 'sync_jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    connection_id: Mapped[str] = mapped_column(ForeignKey('connections.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='running')
    records: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created: Mapped[float] = mapped_column(Float, default=time.time)

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(36))
    created: Mapped[float] = mapped_column(Float, default=time.time)
