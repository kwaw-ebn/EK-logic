"""Read-only Google connectors. Fixed upstream URLs; never accept a remote URL from a user."""
import json
import time
from datetime import date, timedelta
from urllib.parse import quote
import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException
from . import config

SCOPES = {
    'gsc': 'https://www.googleapis.com/auth/webmasters.readonly',
    'ga4': 'https://www.googleapis.com/auth/analytics.readonly',
}

def cipher():
    if not config.CREDENTIAL_KEY:
        raise HTTPException(503, 'Google credential encryption is not configured')
    return Fernet(config.CREDENTIAL_KEY.encode())

def encrypt(value):
    return cipher().encrypt(json.dumps(value).encode()).decode()

def decrypt(value):
    return json.loads(cipher().decrypt(value.encode()))

def configured():
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET and config.CREDENTIAL_KEY)

async def request(method, url, token=None, **kwargs):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(3):
            try:
                response = await client.request(method, url, headers=headers, **kwargs)
            except httpx.RequestError:
                if attempt == 2:
                    raise HTTPException(502, 'Google connection failed; retry later')
                continue
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                break
            import asyncio
            await asyncio.sleep(2 ** attempt)
    if response.status_code >= 400:
        raise HTTPException(502, f'Google API returned HTTP {response.status_code}; check permissions and retry')
    return response.json()

async def access_token(connection):
    tokens = decrypt(connection.encrypted_token)
    if tokens.get('expires_at', 0) > time.time() + 60:
        return tokens['access_token']
    if not tokens.get('refresh_token'):
        raise HTTPException(409, 'Reconnect this Google source to renew access')
    refreshed = await request('POST', 'https://oauth2.googleapis.com/token', data={
        'client_id': config.GOOGLE_CLIENT_ID, 'client_secret': config.GOOGLE_CLIENT_SECRET,
        'grant_type': 'refresh_token', 'refresh_token': tokens['refresh_token']})
    tokens.update(refreshed)
    tokens['expires_at'] = time.time() + refreshed.get('expires_in', 3600)
    connection.encrypted_token = encrypt(tokens)
    return tokens['access_token']

async def properties(provider, token):
    if provider == 'gsc':
        data = await request('GET', 'https://www.googleapis.com/webmasters/v3/sites', token)
        return [{'id': s['siteUrl'], 'name': s['siteUrl']} for s in data.get('siteEntry', [])
                if s.get('permissionLevel') != 'siteUnverifiedUser']
    results = []
    page = None
    while True:
        params = {'pageSize': 200}
        if page:
            params['pageToken'] = page
        data = await request('GET', 'https://analyticsadmin.googleapis.com/v1beta/accountSummaries', token, params=params)
        for account in data.get('accountSummaries', []):
            results.extend({'id': p['property'], 'name': p.get('displayName', p['property'])}
                           for p in account.get('propertySummaries', []))
        page = data.get('nextPageToken')
        if not page:
            return results

async def daily_rows(provider, property_id, token, start, end):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        raise HTTPException(422, 'Use ISO dates YYYY-MM-DD')
    if last < first or (last - first).days > 30 or last >= date.today():
        raise HTTPException(422, 'Select 1–31 completed days')
    current = first
    # Daily aggregate requests avoid query-row limits and are safe to upsert.
    while current <= last:
        day = current.isoformat()
        if provider == 'gsc':
            data = await request('POST', f'https://www.googleapis.com/webmasters/v3/sites/{quote(property_id, safe="")}/searchAnalytics/query', token,
                                 json={'startDate': day, 'endDate': day, 'dataState': 'final', 'type': 'web'})
            row = next(iter(data.get('rows', [])), None)
            # Empty responses must not be silently interpreted as final zero data.
            if row is not None:
                yield day, {k: float(row.get(k, 0)) for k in ('clicks', 'impressions', 'ctr', 'position')}
        else:
            data = await request('POST', f'https://analyticsdata.googleapis.com/v1beta/{property_id}:runReport', token,
                                 json={'dateRanges': [{'startDate': day, 'endDate': day}],
                                       'metrics': [{'name': 'sessions'}, {'name': 'eventCount'}]})
            row = next(iter(data.get('rows', [])), None)
            if row is not None:
                values = row['metricValues']
                yield day, {'sessions': float(values[0]['value']), 'event_count': float(values[1]['value'])}
        current += timedelta(days=1)
