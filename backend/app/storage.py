import os
from pathlib import Path
from .config import STORAGE_DIR

class Storage:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET')
        if self.bucket:
            import boto3
            from botocore.config import Config
            self.client = boto3.client(
                's3', endpoint_url=os.getenv('S3_ENDPOINT_URL') or None,
                config=Config(s3={'addressing_style': 'path'},
                              request_checksum_calculation='when_required',
                              response_checksum_validation='when_required'),
            )
        else:
            Path(STORAGE_DIR).mkdir(parents=True, exist_ok=True)

    def put(self, key, value):
        if self.bucket:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=value,
                                   ContentType='application/octet-stream')
        else:
            (Path(STORAGE_DIR) / key).write_bytes(value)

    def get(self, key):
        if self.bucket:
            return self.client.get_object(Bucket=self.bucket, Key=key)['Body'].read()
        return (Path(STORAGE_DIR) / key).read_bytes()

    def delete(self, key):
        if self.bucket:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        else:
            (Path(STORAGE_DIR) / key).unlink(missing_ok=True)
