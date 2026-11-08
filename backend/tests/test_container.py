import importlib.util
from pathlib import Path


def test_combined_service_keeps_api_on_loopback():
    launcher = Path(__file__).resolve().parents[2] / 'deploy' / 'run.py'
    spec = importlib.util.spec_from_file_location('container_launcher', launcher)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (api, api_directory), (web, web_directory) = module.commands(10000)
    assert api[api.index('--host') + 1] == '127.0.0.1'
    assert api[api.index('--port') + 1] == '8000'
    assert web[web.index('--hostname') + 1] == '0.0.0.0'
    assert web[web.index('--port') + 1] == '10000'
    assert api_directory.name == 'backend'
    assert web_directory.name == 'frontend'
