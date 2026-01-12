"""外观专利 Milvus 服务 (design_patents_full)"""
from pymilvus import Collection, connections, utility
from typing import Optional
import time

from app.config import MILVUS_HOST, MILVUS_PORT

COLLECTION_NAME = "design_patents_full"

SEARCH_PARAMS = {
    "metric_type": "COSINE",
    "params": {"nprobe": 32}
}

# 搜索时返回的字段
OUTPUT_FIELDS = [
    "patent_id", "image_index", "file_name", "file_path",
    "title", "loc_class", "pub_date", "filing_date",
    "applicant_name", "applicant_country", "inventor_names",
    "claim_text", "image_count"
]


class DesignPatentService:
    _instance: Optional["DesignPatentService"] = None
    _collection: Optional[Collection] = None
    _connected: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> bool:
        if self._connected:
            return True
        try:
            connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
            self._connected = True
            return True
        except Exception as e:
            print(f"[DESIGN] Connect failed: {e}")
            return False

    def get_collection(self) -> Collection:
        if not self._connected:
            self.connect()
        if self._collection is None:
            if utility.has_collection(COLLECTION_NAME):
                self._collection = Collection(COLLECTION_NAME)
            else:
                raise RuntimeError(f"Collection '{COLLECTION_NAME}' not found")
        return self._collection

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        min_score: float = 0.5,
        keyword: str = None,
        loc_class: str = None,
        applicant: str = None
    ) -> tuple[list[dict], float]:
        """
        搜索相似图片，支持关键词过滤

        Args:
            query_vector: 768维图像向量
            top_k: 返回数量
            min_score: 最低相似度
            keyword: 关键词（搜索 title）
            loc_class: LOC 分类号
            applicant: 申请人名称
        """
        collection = self.get_collection()

        # 构建过滤表达式
        filters = []
        if keyword:
            filters.append(f'title like "%{keyword}%"')
        if loc_class:
            filters.append(f'loc_class == "{loc_class}"')
        if applicant:
            filters.append(f'applicant_name like "%{applicant}%"')

        expr = " and ".join(filters) if filters else None

        start_time = time.time()
        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=SEARCH_PARAMS,
            limit=top_k * 2,
            expr=expr,
            output_fields=OUTPUT_FIELDS
        )
        search_time_ms = (time.time() - start_time) * 1000

        # 过滤和格式化
        filtered = []
        for hit in results[0]:
            if hit.score >= min_score:
                filtered.append({
                    "id": hit.id,
                    "score": float(hit.score),
                    "patent_id": hit.entity.get("patent_id"),
                    "image_index": hit.entity.get("image_index"),
                    "file_name": hit.entity.get("file_name"),
                    "file_path": hit.entity.get("file_path"),
                    "title": hit.entity.get("title"),
                    "loc_class": hit.entity.get("loc_class"),
                    "pub_date": hit.entity.get("pub_date"),
                    "filing_date": hit.entity.get("filing_date"),
                    "applicant_name": hit.entity.get("applicant_name"),
                    "applicant_country": hit.entity.get("applicant_country"),
                    "inventor_names": hit.entity.get("inventor_names"),
                    "claim_text": hit.entity.get("claim_text"),
                    "image_count": hit.entity.get("image_count"),
                })

        return filtered[:top_k], search_time_ms

    def get_patent_detail(self, patent_id: str) -> list[dict]:
        """获取专利所有图片"""
        collection = self.get_collection()
        results = collection.query(
            expr=f'patent_id == "{patent_id}"',
            output_fields=OUTPUT_FIELDS
        )
        return sorted(results, key=lambda x: x.get("image_index", 0))

    def get_stats(self) -> dict:
        try:
            collection = self.get_collection()
            collection.flush()
            return {
                "name": COLLECTION_NAME,
                "num_entities": collection.num_entities,
                "connected": True
            }
        except Exception as e:
            return {"name": COLLECTION_NAME, "num_entities": 0, "error": str(e)}


design_patent_service = DesignPatentService()
