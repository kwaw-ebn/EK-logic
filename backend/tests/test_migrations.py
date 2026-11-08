import os
import subprocess
import sys

def test_migration_round_trip(tmp_path):
    env = {**os.environ, 'DATABASE_URL': 'sqlite:///' + str(tmp_path / 'migration.db')}
    for args in [('upgrade', 'head'), ('check',), ('downgrade', 'base'), ('upgrade', 'head')]:
        result = subprocess.run([sys.executable, '-m', 'alembic', *args], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr + result.stdout
