import uuid

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class StorageService:
    """
    Обёртка над S3-совместимым объектным хранилищем (MinIO в docker-compose,
    в проде может быть заменено на аттестованное облако без изменения
    остального кода — вся зависимость от boto3 изолирована здесь).
    """

    def __init__(self, client: "boto3.client | None" = None) -> None:
        self._client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        self._bucket = settings.s3_bucket_name

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def upload_file(self, file_bytes: bytes, original_filename: str) -> str:
        """Загружает файл, возвращает ключ объекта в хранилище."""
        object_key = f"{uuid.uuid4()}_{original_filename}"
        self._client.put_object(
            Bucket=self._bucket,
            Key=object_key,
            Body=file_bytes,
            ContentType="application/pdf",
        )
        return object_key

    def download_file(self, object_key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=object_key)
        return response["Body"].read()


storage_service = StorageService()
