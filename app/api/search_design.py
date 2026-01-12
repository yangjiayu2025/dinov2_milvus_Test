"""外观专利搜索 API"""
import time
from collections import defaultdict
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
from PIL import Image
import io
import traceback

from app.config import DEFAULT_TOP_K, DEFAULT_MIN_SCORE
from app.services.design_patent_service import design_patent_service
from app.services.dinov2_base_service import dinov2_base_extractor
from app.services.minio_service import minio_service

router = APIRouter(prefix="/api/design", tags=["design-patent"])

# MinIO 中外观专利图片的前缀
MINIO_PREFIX = "design_patents"


def group_by_patent(results: list[dict]) -> list[dict]:
    """按专利号归组结果，保留完整元数据"""
    groups = defaultdict(lambda: {"pages": [], "metadata": None})

    for r in results:
        patent_id = r["patent_id"]
        groups[patent_id]["pages"].append({
            "id": r["id"],
            "image_index": r["image_index"],
            "file_name": r["file_name"],
            "file_path": r["file_path"],
            "score": r["score"],
        })
        # 保存元数据（只需保存一次）
        if groups[patent_id]["metadata"] is None:
            groups[patent_id]["metadata"] = {
                "title": r["title"],
                "loc_class": r["loc_class"],
                "pub_date": r["pub_date"],
                "filing_date": r["filing_date"],
                "applicant_name": r["applicant_name"],
                "applicant_country": r["applicant_country"],
                "inventor_names": r["inventor_names"],
                "claim_text": r["claim_text"],
                "image_count": r["image_count"],
            }

    # 转换为列表
    result_list = []
    for patent_id, data in groups.items():
        pages = sorted(data["pages"], key=lambda x: x["image_index"])
        max_score = max(p["score"] for p in pages)
        result_list.append({
            "patent_id": patent_id,
            "pages": pages,
            "max_score": max_score,
            **data["metadata"]
        })

    result_list.sort(key=lambda x: x["max_score"], reverse=True)
    return result_list


@router.post("/search")
async def search_design_patents(
    file: UploadFile = File(...),
    top_k: int = Form(DEFAULT_TOP_K),
    min_score: float = Form(DEFAULT_MIN_SCORE),
    keyword: str = Form(None),
    loc_class: str = Form(None),
    applicant: str = Form(None),
):
    """
    外观专利图像搜索（支持关键词过滤）

    - file: 上传的图片（必须）
    - keyword: 关键词，搜索标题（可选）
    - loc_class: LOC 分类号（可选）
    - applicant: 申请人名称（可选）
    """
    print(f"[API-DESIGN] POST /api/design/search")
    print(f"  top_k={top_k}, min_score={min_score}")
    print(f"  keyword={keyword}, loc_class={loc_class}, applicant={applicant}")

    try:
        total_start = time.time()

        # 读取图片
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

        # 提取特征
        query_vector, feature_time_ms = dinov2_base_extractor.extract_from_pil(image)

        # 搜索（带过滤）
        results, search_time_ms = design_patent_service.search(
            query_vector=query_vector,
            top_k=top_k,
            min_score=min_score,
            keyword=keyword,
            loc_class=loc_class,
            applicant=applicant
        )

        # 归组
        post_start = time.time()
        grouped_results = group_by_patent(results)
        post_process_ms = (time.time() - post_start) * 1000

        total_ms = (time.time() - total_start) * 1000

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
                    "keyword": keyword,
                    "loc_class": loc_class,
                    "applicant": applicant,
                    "total_matched": len(results),
                }
            }
        }
    except Exception as e:
        print(f"[API-DESIGN] Search error: {e}")
        traceback.print_exc()
        return {"code": 1, "message": str(e), "data": None}


@router.get("/patent/{patent_id}")
async def get_patent_detail(patent_id: str):
    """获取专利详情（所有图片）"""
    try:
        results = design_patent_service.get_patent_detail(patent_id)
        if not results:
            return {"code": 1, "message": "Patent not found", "data": None}

        return {
            "code": 0,
            "data": {
                "patent_id": patent_id,
                "images": results,
                "metadata": {
                    "title": results[0].get("title"),
                    "loc_class": results[0].get("loc_class"),
                    "pub_date": results[0].get("pub_date"),
                    "filing_date": results[0].get("filing_date"),
                    "applicant_name": results[0].get("applicant_name"),
                    "applicant_country": results[0].get("applicant_country"),
                    "inventor_names": results[0].get("inventor_names"),
                    "claim_text": results[0].get("claim_text"),
                    "image_count": results[0].get("image_count"),
                }
            }
        }
    except Exception as e:
        traceback.print_exc()
        return {"code": 1, "message": str(e), "data": None}


@router.get("/stats")
async def get_design_stats():
    """获取 Collection 统计"""
    try:
        stats = design_patent_service.get_stats()
        device_info = dinov2_base_extractor.get_device_info()
        return {
            "code": 0,
            "data": {"collection": stats, "model": device_info}
        }
    except Exception as e:
        return {"code": 1, "message": str(e), "data": None}


@router.get("/image/{patent_id}/{file_name}")
async def get_design_image(
    patent_id: str,
    file_name: str,
    thumbnail: bool = Query(False, description="是否返回缩略图")
):
    """
    获取外观专利图片（自动转换为浏览器可显示格式）

    - patent_id: 专利号，如 USD1012345
    - file_name: 文件名，如 USD10123450001.TIF
    - thumbnail: 是否返回缩略图（默认 False）
    """
    try:
        minio_service.connect()

        # 构建 MinIO 对象路径
        object_name = f"{MINIO_PREFIX}/{patent_id}/{file_name}"

        # 从 MinIO 下载图片
        data = minio_service.download_file(object_name)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Image not found: {object_name}")

        # 用 PIL 打开并转换
        img = Image.open(io.BytesIO(data))

        # 处理多帧图片（如 TIF）
        if hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(0)

        # 转换为 RGB
        img = img.convert("RGB")

        # 如果是缩略图，调整大小
        if thumbnail:
            img.thumbnail((300, 300), Image.Resampling.LANCZOS)

        # 转换为 JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85 if thumbnail else 95)
        buffer.seek(0)

        return StreamingResponse(buffer, media_type="image/jpeg")

    except HTTPException:
        raise
    except Exception as e:
        print(f"[API-DESIGN] Image error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process image: {e}")
