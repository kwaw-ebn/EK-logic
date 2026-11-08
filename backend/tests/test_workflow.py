import io
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from conftest import register

CSV = b'date,district,visits,revenue\n2026-01-01,Agona East,10,100\n2026-01-02,Winneba,20,200\n2026-01-03,Agona East,30,300\n'

def upload(client, workspace, raw=CSV, name='activity.csv'):
    response = client.post(f'/workspaces/{workspace}/datasets', files={'file': (name, raw)})
    assert response.status_code == 201, response.text
    return response.json()

def test_complete_upload_analysis_export_workflow(client):
    workspace = register(client)
    ds = upload(client, workspace)
    assert ds['profile']['rows'] == 3
    assert ds['profile']['columns'][0]['type'] == 'date'
    chart = client.get(f'/datasets/{ds["id"]}/chart', params={'dimension': 'district', 'measure': 'visits', 'operation': 'sum'})
    assert chart.status_code == 200
    assert chart.json()['points'] == [{'label': 'Agona East', 'value': 40}, {'label': 'Winneba', 'value': 20}]
    saved = client.post(f'/datasets/{ds["id"]}/analyses', json={'name': 'Visits', 'dimension': 'district', 'measure': 'visits', 'operation': 'sum'})
    assert saved.status_code == 201
    analysis_id = saved.json()['id']
    assert client.get(f'/workspaces/{workspace}/analyses').json()[0]['id'] == analysis_id
    csv = client.get(f'/analyses/{analysis_id}/export?format=csv')
    assert b'Agona East,40.0' in csv.content
    xlsx = client.get(f'/analyses/{analysis_id}/export?format=xlsx')
    book = pd.ExcelFile(io.BytesIO(xlsx.content))
    assert book.sheet_names == ['Analysis', 'Metadata']
    pdf = client.get(f'/analyses/{analysis_id}/export?format=pdf')
    assert pdf.content.startswith(b'%PDF')
    assert client.post('/auth/logout').status_code == 204
    assert client.get('/auth/me').status_code == 401
    assert client.post('/auth/login', json={'email': 'analyst@example.com', 'password': 'a-long-secure-password'}).status_code == 200
    assert client.get(f'/datasets/{ds["id"]}').status_code == 200

def test_cross_tenant_read_write_and_export_blocked(client):
    workspace = register(client)
    ds = upload(client, workspace)
    saved = client.post(f'/datasets/{ds["id"]}/analyses', json={'name': 'Visits', 'dimension': 'district', 'measure': 'visits', 'operation': 'sum'}).json()
    with TestClient(app, headers={'x-ek-request': '1'}) as other:
        register(other, 'other@example.com')
        for path in [f'/datasets/{ds["id"]}', f'/workspaces/{workspace}/datasets', f'/workspaces/{workspace}/analyses',
                     f'/datasets/{ds["id"]}/chart?dimension=district&measure=visits', f'/analyses/{saved["id"]}/export',
                     f'/workspaces/{workspace}/connections', f'/workspaces/{workspace}/marketing?start=2026-01-01&end=2026-01-02']:
            assert other.get(path).status_code == 404, path
        assert other.put(f'/datasets/{ds["id"]}/meanings', json={'meanings': ds['meanings']}).status_code == 404
        assert other.post(f'/workspaces/{workspace}/datasets', files={'file': ('x.csv', CSV)}).status_code == 404
        assert other.post(f'/workspaces/{workspace}/google/gsc/authorize').status_code == 404

def test_missing_duplicate_values_are_preserved(client):
    workspace = register(client)
    ds = upload(client, workspace, b'group,value\na,1\na,1\nb,\n')
    assert ds['profile']['duplicate_rows'] == 1
    assert ds['profile']['missing_cells'] == 1
    chart = client.get(f'/datasets/{ds["id"]}/chart?dimension=group&measure=value').json()
    assert chart['points'] == [{'label': 'a', 'value': 2}, {'label': 'b', 'value': None}]

def test_excel_sheet_selection(client):
    workspace = register(client)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame({'area': ['A'], 'count': [5]}).to_excel(writer, sheet_name='First', index=False)
        pd.DataFrame({'area': ['B', 'C'], 'count': [10, 20]}).to_excel(writer, sheet_name='Second', index=False)
    response = client.post(f'/workspaces/{workspace}/datasets', files={'file': ('test.xlsx', output.getvalue())}, data={'sheet': 'Second'})
    assert response.status_code == 201
    ds = response.json()
    assert ds['profile']['rows'] == 2
    assert ds['profile']['selected_sheet'] == 'Second'
    assert ds['profile']['sheets'] == ['First', 'Second']

def test_upload_validation_and_aggregation_allowlist(client):
    workspace = register(client)
    assert client.post(f'/workspaces/{workspace}/datasets', files={'file': ('run.py', b'print(1)')}).status_code == 422
    assert client.post(f'/workspaces/{workspace}/datasets', files={'file': ('broken.xlsx', b'broken')}).status_code == 422
    assert client.post(f'/workspaces/{workspace}/datasets', files={'file': ('empty.csv', b'')}).status_code == 422
    assert client.post(f'/workspaces/{workspace}/datasets', files={'file': ('huge.csv', b'x' * (10 * 1024 * 1024 + 1))}).status_code == 413
    ds = upload(client, workspace)
    assert client.get(f'/datasets/{ds["id"]}/chart?dimension=district&measure=visits&operation=exec').status_code == 422
    assert client.get(f'/datasets/{ds["id"]}/chart?dimension=district&measure=district').status_code == 422
    assert client.put(f'/datasets/{ds["id"]}/meanings', json={'meanings': {'unknown': 'measure'}}).status_code == 422

def test_csrf_cookie_and_password_rules(client):
    assert client.post('/auth/register', json={'name': 'A', 'organization': 'A', 'email': 'a@example.com', 'password': 'short'}).status_code == 422
    register(client)
    assert client.cookies.get('ek_session')
    assert client.post('/workspaces', json={'name': 'Bad origin'}, headers={'origin': 'https://evil.example'}).status_code == 403
    with TestClient(app) as no_header:
        assert no_header.post('/auth/login', json={'email': 'a@example.com', 'password': 'passwordpassword'}).status_code == 403
    assert client.post('/auth/register', json={'name': 'A', 'organization': 'A', 'email': 'analyst@example.com', 'password': 'passwordpassword'}).status_code == 409

def test_export_formula_injection_protection(client):
    workspace = register(client)
    ds = upload(client, workspace, b'group,value\n=HYPERLINK("evil"),2\n@SUM(1),3\n')
    saved = client.post(f'/datasets/{ds["id"]}/analyses', json={'name': '=evil', 'dimension': 'group', 'measure': 'value', 'operation': 'sum'}).json()
    export = client.get(f'/analyses/{saved["id"]}/export?format=csv').content.decode('utf-8-sig')
    assert "'=HYPERLINK" in export
    assert "'@SUM" in export

def test_google_is_explicitly_unconfigured(client):
    workspace = register(client)
    assert client.get('/integrations/status').json()['google_configured'] is False
    assert client.post(f'/workspaces/{workspace}/google/gsc/authorize').status_code == 503


def test_access_logs_redact_oauth_query_parameters():
    import logging
    from app.main import RedactQuery
    record = logging.LogRecord('uvicorn.access', 20, '', 0, '%s %s %s %s %s',
                               ('127.0.0.1', 'GET', '/google/callback?code=secret&state=secret', '1.1', 200), None)
    assert RedactQuery().filter(record)
    assert record.args[2] == '/google/callback'
    assert 'secret' not in record.getMessage()
