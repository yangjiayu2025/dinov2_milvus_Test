"""批量导入 API (Base 模型)"""
import traceback
from fastapi import APIRouter

from app.services.batch_import_base_service import batch_import_base_service

router = APIRouter(prefix="/api/base/batch", tags=["batch-base"])


@router.post("/start")
async def start_batch_import_base():
    """启动批量导入 (Base 模型)"""
    print("[API-BASE] POST /api/base/batch/start called")

    try:
        if batch_import_base_service.status == "running":
            print("[API-BASE] Import already running")
            return {
                "code": 1,
                "message": "Import already running",
                "data": batch_import_base_service.get_status()
            }

        # 启动导入（在后台线程中运行）
        print("[API-BASE] Starting batch import...")
        batch_import_base_service.start_import()

        status = batch_import_base_service.get_status()
        print(f"[API-BASE] Import started, status: {status}")

        return {
            "code": 0,
            "message": "Import started",
            "data": status
        }
    except Exception as e:
        print(f"[API-BASE] start_batch_import error: {e}")
        traceback.print_exc()
        return {
            "code": 1,
            "message": str(e),
            "data": None
        }


@router.get("/status")
async def get_batch_status_base():
    """获取导入进度 (Base 模型)"""
    try:
        status = batch_import_base_service.get_status()
        return {
            "code": 0,
            "data": status
        }
    except Exception as e:
        print(f"[API-BASE] get_batch_status error: {e}")
        traceback.print_exc()
        return {
            "code": 1,
            "message": str(e),
            "data": {
                "status": "error",
                "error_message": str(e)
            }
        }


@router.post("/reset")
async def reset_batch_status_base():
    """重置导入状态（用于错误恢复）(Base 模型)"""
    print("[API-BASE] POST /api/base/batch/reset called")

    try:
        if batch_import_base_service.status == "running":
            return {
                "code": 1,
                "message": "Cannot reset while running"
            }

        batch_import_base_service.status = "idle"
        batch_import_base_service.processed = 0
        batch_import_base_service.failed = []
        batch_import_base_service.error_message = None

        print("[API-BASE] Status reset to idle")
        return {
            "code": 0,
            "message": "Status reset"
        }
    except Exception as e:
        print(f"[API-BASE] reset_batch_status error: {e}")
        traceback.print_exc()
        return {
            "code": 1,
            "message": str(e)
        }
