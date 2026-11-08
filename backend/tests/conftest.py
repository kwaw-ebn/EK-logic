import os
import tempfile
os.environ['DATABASE_URL'] = os.getenv('TEST_DATABASE_URL') or 'sqlite:///' + tempfile.mktemp(suffix='.db')
os.environ['STORAGE_DIR'] = tempfile.mkdtemp()
import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine
from app.main import app, buckets

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    buckets.clear()
    yield

@pytest.fixture
def client():
    with TestClient(app, headers={'x-ek-request': '1'}) as client:
        yield client

def register(client, email='analyst@example.com'):
    response = client.post('/auth/register', json={'name': 'Analyst', 'email': email,
        'password': 'a-long-secure-password', 'organization': 'Research organization'})
    assert response.status_code == 201, response.text
    return client.get('/workspaces').json()[0]['id']
