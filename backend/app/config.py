import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./eklogic.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
PRODUCTION = os.getenv('APP_ENV', 'development') == 'production'
# Render supplies its assigned canonical URL at runtime; never derive trust from request headers.
FRONTEND_URL = (os.getenv('FRONTEND_URL') or os.getenv('RENDER_EXTERNAL_URL') or 'http://localhost:3000').rstrip('/')
STORAGE_DIR = os.getenv('STORAGE_DIR', './data')
MAX_UPLOAD = 10 * 1024 * 1024
MAX_ROWS = 100000
MAX_COLUMNS = 100
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI') or FRONTEND_URL + '/api/google/callback'
CREDENTIAL_KEY = os.getenv('CREDENTIAL_KEY', '')
if PRODUCTION and not DATABASE_URL.startswith('postgresql'):
    raise RuntimeError('Production requires PostgreSQL')
if PRODUCTION and not FRONTEND_URL.startswith('https://'):
    raise RuntimeError('Production requires HTTPS FRONTEND_URL')

if CREDENTIAL_KEY:
    from cryptography.fernet import Fernet
    Fernet(CREDENTIAL_KEY.encode())
if PRODUCTION and not os.getenv('S3_BUCKET'):
    raise RuntimeError('Production requires a private S3-compatible bucket for durable uploads')
