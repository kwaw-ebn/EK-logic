import io
from unittest.mock import Mock
import boto3
from app.storage import Storage


def test_private_s3_round_trip_and_path_style(monkeypatch):
    monkeypatch.setenv('S3_BUCKET', 'eklogic-uploads')
    monkeypatch.setenv('S3_ENDPOINT_URL', 'https://storage.example.test')
    client = Mock()
    client.get_object.return_value = {'Body': io.BytesIO(b'group,value\na,2\n')}
    factory = Mock(return_value=client)
    monkeypatch.setattr(boto3, 'client', factory)
    storage = Storage()
    assert factory.call_args.kwargs['endpoint_url'] == 'https://storage.example.test'
    options = factory.call_args.kwargs['config']
    assert options.s3['addressing_style'] == 'path'
    assert options.request_checksum_calculation == 'when_required'
    storage.put('opaque-key', b'group,value\na,2\n')
    client.put_object.assert_called_once_with(Bucket='eklogic-uploads', Key='opaque-key',
                                              Body=b'group,value\na,2\n', ContentType='application/octet-stream')
    assert storage.get('opaque-key') == b'group,value\na,2\n'
    storage.delete('opaque-key')
    client.delete_object.assert_called_once_with(Bucket='eklogic-uploads', Key='opaque-key')
