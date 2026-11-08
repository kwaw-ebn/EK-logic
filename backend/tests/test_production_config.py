import os
import subprocess
import sys
import pytest


def config_process(origin, override=None):
    env = {**os.environ, 'APP_ENV': 'production', 'DATABASE_URL': 'postgresql://db.example/eklogic',
           'S3_BUCKET': 'private-uploads', 'RENDER_EXTERNAL_URL': origin}
    env.pop('FRONTEND_URL', None)
    env.pop('GOOGLE_REDIRECT_URI', None)
    if override:
        env['FRONTEND_URL'] = override
    return subprocess.run([sys.executable, '-c',
                           'from app.config import FRONTEND_URL, GOOGLE_REDIRECT_URI; print(FRONTEND_URL); print(GOOGLE_REDIRECT_URI)'],
                          env=env, capture_output=True, text=True)


def test_single_service_uses_provider_assigned_https_origin():
    result = config_process('https://ek-logic-assigned.onrender.com')
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ['https://ek-logic-assigned.onrender.com',
                                         'https://ek-logic-assigned.onrender.com/api/google/callback']


def test_custom_frontend_origin_overrides_provider_default():
    result = config_process('https://api.example.com', 'https://app.example.com/')
    assert result.returncode == 0
    assert result.stdout.splitlines()[0] == 'https://app.example.com'


def test_insecure_production_origin_is_rejected():
    result = config_process('http://insecure.example')
    assert result.returncode != 0
    assert 'Production requires HTTPS FRONTEND_URL' in result.stderr
