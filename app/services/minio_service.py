"""MinIO 对象存储服务"""
import os
import io
from typing import Optional
from minio import Minio
from minio.error import S3Error

from app.config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
    MINIO_SECURE
)


class MinIOService:
    """MinIO 服务封装"""
    _instance: Optional["MinIOService"] = None
    _client: Optional[Minio] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> bool:
        """连接 MinIO"""
        if self._client is not None:
            return True

        try:
            print(f"[MINIO] Connecting to {MINIO_ENDPOINT}...")
            self._client = Minio(
                MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE
            )

            # 检查 bucket 是否存在
            if not self._client.bucket_exists(MINIO_BUCKET):
                print(f"[MINIO] Bucket '{MINIO_BUCKET}' does not exist, creating...")
                self._client.make_bucket(MINIO_BUCKET)
                print(f"[MINIO] Bucket '{MINIO_BUCKET}' created")
            else:
                print(f"[MINIO] Bucket '{MINIO_BUCKET}' exists")

            print(f"[MINIO] Connected successfully")
            return True
        except Exception as e:
            print(f"[MINIO] Failed to connect: {e}")
            return False

    def get_client(self) -> Minio:
        """获取 MinIO 客户端"""
        if self._client is None:
            self.connect()
        return self._client

    def upload_file(self, local_path: str, object_name: str) -> Optional[str]:
        """
        上传文件到 MinIO

        Args:
            local_path: 本地文件路径
            object_name: MinIO 对象名 (如 'testImage/xxx.TIF')

        Returns:
            成功返回 MinIO URL，失败返回 None
        """
        try:
            client = self.get_client()

            # 获取文件大小和类型
            file_size = os.path.getsize(local_path)
            content_type = self._get_content_type(local_path)

            # 上传
            client.fput_object(
                MINIO_BUCKET,
                object_name,
                local_path,
                content_type=content_type
            )

            # 返回 URL
            url = self.get_url(object_name)
            return url
        except S3Error as e:
            print(f"[MINIO] Failed to upload {local_path}: {e}")
            return None
        except Exception as e:
            print(f"[MINIO] Upload error: {e}")
            return None

    def upload_bytes(self, data: bytes, object_name: str, content_type: str = "application/octet-stream") -> Optional[str]:
        """
        上传字节数据到 MinIO

        Args:
            data: 字节数据
            object_name: MinIO 对象名
            content_type: 内容类型

        Returns:
            成功返回 MinIO URL，失败返回 None
        """
        try:
            client = self.get_client()

            data_stream = io.BytesIO(data)
            data_length = len(data)

            client.put_object(
                MINIO_BUCKET,
                object_name,
                data_stream,
                data_length,
                content_type=content_type
            )

            return self.get_url(object_name)
        except Exception as e:
            print(f"[MINIO] Failed to upload bytes: {e}")
            return None

    def download_file(self, object_name: str) -> Optional[bytes]:
        """
        从 MinIO 下载文件

        Args:
            object_name: MinIO 对象名

        Returns:
            文件字节数据，失败返回 None
        """
        try:
            client = self.get_client()
            response = client.get_object(MINIO_BUCKET, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            print(f"[MINIO] Failed to download {object_name}: {e}")
            return None
        except Exception as e:
            print(f"[MINIO] Download error: {e}")
            return None

    def file_exists(self, object_name: str) -> bool:
        """检查文件是否存在"""
        try:
            client = self.get_client()
            client.stat_object(MINIO_BUCKET, object_name)
            return True
        except S3Error:
            return False
        except Exception:
            return False

    def get_url(self, object_name: str) -> str:
        """获取文件的 HTTP URL"""
        protocol = "https" if MINIO_SECURE else "http"
        return f"{protocol}://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{object_name}"

    def parse_minio_url(self, url: str) -> Optional[str]:
        """
        从 MinIO URL 解析出 object_name

        Args:
            url: MinIO URL

        Returns:
            object_name，失败返回 None
        """
        prefix = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/"
        prefix_https = f"https://{MINIO_ENDPOINT}/{MINIO_BUCKET}/"

        if url.startswith(prefix):
            return url[len(prefix):]
        elif url.startswith(prefix_https):
            return url[len(prefix_https):]
        return None

    def _get_content_type(self, file_path: str) -> str:
        """根据文件扩展名获取 content-type"""
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }
        return content_types.get(ext, "application/octet-stream")

    def list_objects(self, prefix: str = "") -> list[str]:
        """列出指定前缀的所有对象"""
        try:
            client = self.get_client()
            objects = client.list_objects(MINIO_BUCKET, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except Exception as e:
            print(f"[MINIO] Failed to list objects: {e}")
            return []


# 单例实例
minio_service = MinIOService()
