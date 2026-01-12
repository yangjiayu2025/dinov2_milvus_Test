"""图片服务 API"""
import os
import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image

from app.config import IMAGE_DIRS, THUMBNAIL_DIR, MINIO_ENDPOINT, MINIO_BUCKET
from app.services.minio_service import minio_service

router = APIRouter(prefix="/api/image", tags=["image"])


def find_image(file_name: str) -> str | None:
    """从多个目录查找图片"""
    for image_dir in IMAGE_DIRS:
        path = os.path.join(image_dir, file_name)
        if os.path.exists(path):
            return path
    return None


def get_minio_object_name(file_name: str) -> str | None:
    """根据文件名确定 MinIO 对象名"""
    # 尝试 testImage 目录
    object_name = f"testImage/{file_name}"
    if minio_service.file_exists(object_name):
        return object_name

    # 尝试 ruiguan 目录
    object_name = f"ruiguan/{file_name}"
    if minio_service.file_exists(object_name):
        return object_name

    return None


def load_image_from_minio(object_name: str) -> Image.Image | None:
    """从 MinIO 加载图片"""
    try:
        data = minio_service.download_file(object_name)
        if data:
            img = Image.open(io.BytesIO(data))
            return img
    except Exception as e:
        print(f"[IMAGE] Failed to load from MinIO: {e}")
    return None


@router.get("/{file_name}")
async def get_thumbnail(file_name: str):
    """获取缩略图"""
    # 去掉扩展名，换成 .jpg
    name, _ = os.path.splitext(file_name)
    thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{name}.jpg")

    if os.path.exists(thumbnail_path):
        return FileResponse(thumbnail_path, media_type="image/jpeg")

    # 尝试从本地多个目录查找原图
    original_path = find_image(file_name)
    img = None

    if original_path:
        try:
            img = Image.open(original_path)
        except Exception as e:
            print(f"[IMAGE] Failed to open local file: {e}")

    # 如果本地没找到，尝试从 MinIO 获取
    if img is None:
        minio_service.connect()
        object_name = get_minio_object_name(file_name)
        if object_name:
            img = load_image_from_minio(object_name)

    if img is None:
        raise HTTPException(status_code=404, detail="Image not found")

    # 实时转换
    try:
        if hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(0)
        img = img.convert("RGB")
        img.thumbnail((300, 300), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        return StreamingResponse(buffer, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process image: {e}")


@router.get("/full/{file_name}")
async def get_full_image(file_name: str):
    """获取原图（转换为 JPEG）"""
    original_path = find_image(file_name)
    img = None

    if original_path:
        try:
            img = Image.open(original_path)
        except Exception as e:
            print(f"[IMAGE] Failed to open local file: {e}")

    # 如果本地没找到，尝试从 MinIO 获取
    if img is None:
        minio_service.connect()
        object_name = get_minio_object_name(file_name)
        if object_name:
            img = load_image_from_minio(object_name)

    if img is None:
        raise HTTPException(status_code=404, detail="Image not found")

    try:
        if hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(0)
        img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=95)
        buffer.seek(0)

        return StreamingResponse(buffer, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process image: {e}")
