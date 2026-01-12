"""上传睿观目录到 MinIO"""
import os
import sys
import json
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import SUPPORTED_IMAGE_FORMATS
from app.services.minio_service import minio_service

# 配置
LOCAL_DIR = "睿观"
MINIO_PREFIX = "ruiguan"  # MinIO 中的目录前缀 (使用英文)
PROGRESS_FILE = "睿观/upload_progress.json"


def load_progress() -> set:
    """加载已上传的文件列表"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("uploaded", []))
        except Exception as e:
            print(f"[RUIGUAN] Failed to load progress: {e}")
    return set()


def save_progress(uploaded: set):
    """保存进度"""
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "uploaded": list(uploaded),
                "last_update": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[RUIGUAN] Failed to save progress: {e}")


def scan_images() -> list:
    """扫描本地图片"""
    images = []
    for filename in os.listdir(LOCAL_DIR):
        ext = os.path.splitext(filename)[1].lower()
        if ext in SUPPORTED_IMAGE_FORMATS:
            images.append(filename)
    return sorted(images)


def main():
    print("[RUIGUAN] ========== Upload 睿观 to MinIO ==========")
    print(f"[RUIGUAN] Local directory: {LOCAL_DIR}")
    print(f"[RUIGUAN] MinIO prefix: {MINIO_PREFIX}")

    # 连接 MinIO
    if not minio_service.connect():
        print("[RUIGUAN] Failed to connect to MinIO")
        return

    # 加载进度
    uploaded = load_progress()
    print(f"[RUIGUAN] Already uploaded: {len(uploaded)} files")

    # 扫描图片
    all_images = scan_images()
    print(f"[RUIGUAN] Total images: {len(all_images)}")

    # 过滤已上传的
    pending = [img for img in all_images if img not in uploaded]
    print(f"[RUIGUAN] Pending: {len(pending)} files")

    if not pending:
        print("[RUIGUAN] All files already uploaded!")
        return

    # 开始上传
    success_count = 0
    fail_count = 0

    for i, filename in enumerate(pending):
        local_path = os.path.join(LOCAL_DIR, filename)
        object_name = f"{MINIO_PREFIX}/{filename}"

        url = minio_service.upload_file(local_path, object_name)

        if url:
            uploaded.add(filename)
            success_count += 1
            print(f"[RUIGUAN] Uploaded: {filename}")
        else:
            fail_count += 1
            print(f"[RUIGUAN] Failed: {filename}")

    # 保存进度
    save_progress(uploaded)

    print("[RUIGUAN] ========== Upload completed ==========")
    print(f"[RUIGUAN] Success: {success_count}, Failed: {fail_count}")
    print(f"[RUIGUAN] Total uploaded: {len(uploaded)}")


if __name__ == "__main__":
    main()
