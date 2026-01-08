"""搜索 API (Base 模型)"""
import time
from collections import defaultdict
from fastapi import APIRouter, UploadFile, File, Form
from PIL import Image
import io
import traceback

from app.config import DEFAULT_TOP_K, DEFAULT_MIN_SCORE
from app.services.milvus_base_service import milvus_base_service
from app.services.dinov2_base_service import dinov2_base_extractor

router = APIRouter(prefix="/api/base", tags=["search-base"])


def group_by_patent(results: list[dict]) -> list[dict]:
    """按专利号归组结果"""
    groups = defaultdict(list)

    for r in results:
        groups[r["patent_id"]].append({
            "id": r["id"],
            "file_name": r["file_name"],
            "page_num": r["page_num"],
            "score": r["score"],
            "thumbnail_url": f"/api/image/{r['file_name']}",
        })

    # 转换为列表，计算每组最高分
    result_list = []
    for patent_id, pages in groups.items():
        # 按页码排序
        pages.sort(key=lambda x: x["page_num"])
        max_score = max(p["score"] for p in pages)
        result_list.append({
            "patent_id": patent_id,
            "pages": pages,
            "max_score": max_score,
        })

    # 按最高分降序排列
    result_list.sort(key=lambda x: x["max_score"], reverse=True)

    return result_list


@router.post("/search")
async def search_image_base(
    file: UploadFile = File(...),
    top_k: int = Form(DEFAULT_TOP_K),
    min_score: float = Form(DEFAULT_MIN_SCORE),
):
    """以图搜图 (Base 模型)"""
    print(f"[API-BASE] POST /api/base/search, top_k={top_k}, min_score={min_score}")

    try:
        total_start = time.time()

        # 读取上传的图片
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # 提取特征
        query_vector, feature_time_ms = dinov2_base_extractor.extract_from_pil(image)

        # 搜索
        results, search_time_ms = milvus_base_service.search(
            query_vector=query_vector,
            top_k=top_k,
            min_score=min_score
        )

        # 归组
        post_start = time.time()
        grouped_results = group_by_patent(results)
        post_process_ms = (time.time() - post_start) * 1000

        total_ms = (time.time() - total_start) * 1000

        print(f"[API-BASE] Search completed in {total_ms:.1f}ms, found {len(results)} results")

        return {
            "code": 0,
            "message": "success",
            "data": {
                "results": grouped_results,
                "timing": {
                    "feature_extraction_ms": round(feature_time_ms, 2),
                    "milvus_search_ms": round(search_time_ms, 2),
                    "post_process_ms": round(post_process_ms, 2),
                    "total_ms": round(total_ms, 2),
                },
                "query_info": {
                    "top_k": top_k,
                    "min_score": min_score,
                    "total_matched": len(results),
                    "model": "dinov2-base",
                    "embedding_dim": 768,
                }
            }
        }
    except Exception as e:
        print(f"[API-BASE] Search error: {e}")
        traceback.print_exc()
        return {
            "code": 1,
            "message": str(e),
            "data": None
        }


@router.get("/collection/stats")
async def get_collection_stats_base():
    """获取 Collection 统计信息 (Base 模型)"""
    print("[API-BASE] GET /api/base/collection/stats")

    try:
        stats = milvus_base_service.get_stats()
        device_info = dinov2_base_extractor.get_device_info()

        return {
            "code": 0,
            "data": {
                "collection": stats,
                "model": device_info,
            }
        }
    except Exception as e:
        print(f"[API-BASE] get_collection_stats error: {e}")
        traceback.print_exc()
        return {
            "code": 1,
            "message": str(e),
            "data": {
                "collection": {"num_entities": 0, "error": str(e)},
                "model": {"initialized": False, "error": str(e)},
            }
        }
