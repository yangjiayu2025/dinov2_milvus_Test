"""上传 testImage 目录到 MinIO"""
import os
import sys
import json
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import SUPPORTED_IMAGE_FORMATS
from app.services.minio_service import minio_service

# 配置
LOCAL_DIR = "testImage"
MINIO_PREFIX = "testImage"  # MinIO 中的目录前缀
PROGRESS_FILE = "testImage/upload_progress.json"


def load_progress() -> set:
    """加载已上传的文件列表"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("uploaded", []))
        except Exception as e:
            print(f"[UPLOAD] Failed to load progress: {e}")
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
        print(f"[UPLOAD] Failed to save progress: {e}")


def scan_images() -> list:
    """扫描本地图片"""
    images = []
    for filename in os.listdir(LOCAL_DIR):
        ext = os.path.splitext(filename)[1].lower()
        if ext in SUPPORTED_IMAGE_FORMATS:
            images.append(filename)
    return sorted(images)


def main():
    print("[UPLOAD] ========== Upload testImage to MinIO ==========")
    print(f"[UPLOAD] Local directory: {LOCAL_DIR}")
    print(f"[UPLOAD] MinIO prefix: {MINIO_PREFIX}")

    # 连接 MinIO
    if not minio_service.connect():
        print("[UPLOAD] Failed to connect to MinIO")
        return

    # 加载进度
    uploaded = load_progress()
    print(f"[UPLOAD] Already uploaded: {len(uploaded)} files")

    # 扫描图片
    all_images = scan_images()
    print(f"[UPLOAD] Total images: {len(all_images)}")

    # 过滤已上传的
    pending = [img for img in all_images if img not in uploaded]
    print(f"[UPLOAD] Pending: {len(pending)} files")

    if not pending:
        print("[UPLOAD] All files already uploaded!")
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

            # 每 100 个保存一次进度
            if success_count % 100 == 0:
                save_progress(uploaded)
                progress = (i + 1) / len(pending) * 100
                print(f"[UPLOAD] Progress: {i + 1}/{len(pending)} ({progress:.1f}%)")
        else:
            fail_count += 1
            print(f"[UPLOAD] Failed: {filename}")

    # 最终保存进度
    save_progress(uploaded)

    print("[UPLOAD] ========== Upload completed ==========")
    print(f"[UPLOAD] Success: {success_count}, Failed: {fail_count}")
    print(f"[UPLOAD] Total uploaded: {len(uploaded)}")


if __name__ == "__main__":
    main()
