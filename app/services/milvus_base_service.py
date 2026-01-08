"""Milvus 向量数据库服务 (Base 模型)"""
from pymilvus import (
    connections,
    Collection,
    FieldSchema,
    CollectionSchema,
    DataType,
    utility
)
from typing import Optional
import time

from app.config import (
    MILVUS_HOST,
    MILVUS_PORT,
    COLLECTION_NAME_BASE,
    EMBEDDING_DIM_BASE,
    INDEX_PARAMS,
    SEARCH_PARAMS
)


class MilvusBaseService:
    _instance: Optional["MilvusBaseService"] = None
    _collection: Optional[Collection] = None
    _connected: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> bool:
        """连接 Milvus"""
        if self._connected:
            print(f"[MILVUS-BASE] Already connected")
            return True

        try:
            print(f"[MILVUS-BASE] Connecting to {MILVUS_HOST}:{MILVUS_PORT}...")
            connections.connect(
                alias="default",
                host=MILVUS_HOST,
                port=MILVUS_PORT
            )
            self._connected = True
            print(f"[MILVUS-BASE] Connected successfully")
            return True
        except Exception as e:
            print(f"[MILVUS-BASE] Failed to connect: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_collection(self) -> Collection:
        """创建 Collection"""
        print(f"[MILVUS-BASE] Checking collection '{COLLECTION_NAME_BASE}'...")

        if utility.has_collection(COLLECTION_NAME_BASE):
            print(f"[MILVUS-BASE] Collection '{COLLECTION_NAME_BASE}' already exists")
            self._collection = Collection(COLLECTION_NAME_BASE)
            return self._collection

        print(f"[MILVUS-BASE] Creating collection '{COLLECTION_NAME_BASE}'...")
        print(f"[MILVUS-BASE] Defining schema with dim={EMBEDDING_DIM_BASE}...")
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=256),
            FieldSchema(name="patent_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="page_num", dtype=DataType.VARCHAR, max_length=16),
            FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=512),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM_BASE),
            FieldSchema(name="created_at", dtype=DataType.INT64),
        ]
        print(f"[MILVUS-BASE] Schema defined with {len(fields)} fields")

        schema = CollectionSchema(fields, description="Patent image embeddings (Base model)")
        print(f"[MILVUS-BASE] CollectionSchema created, now creating Collection...")

        self._collection = Collection(name=COLLECTION_NAME_BASE, schema=schema)
        print(f"[MILVUS-BASE] Collection '{COLLECTION_NAME_BASE}' created successfully")

        return self._collection

    def create_index(self) -> bool:
        """创建索引"""
        if self._collection is None:
            self._collection = Collection(COLLECTION_NAME_BASE)

        # 检查是否已有索引
        if self._collection.has_index():
            print("[MILVUS-BASE] Index already exists")
            return True

        print(f"[MILVUS-BASE] Creating index with params: {INDEX_PARAMS}")
        self._collection.create_index(
            field_name="embedding",
            index_params=INDEX_PARAMS
        )
        print("[MILVUS-BASE] Index created successfully")
        return True

    def load_collection(self) -> bool:
        """加载 Collection 到内存"""
        if self._collection is None:
            self._collection = Collection(COLLECTION_NAME_BASE)

        print(f"[MILVUS-BASE] Loading collection '{COLLECTION_NAME_BASE}'...")
        self._collection.load()
        print(f"[MILVUS-BASE] Collection loaded")
        return True

    def get_collection(self) -> Collection:
        """获取 Collection 实例"""
        if not self._connected:
            raise RuntimeError("Milvus not connected. Please check Milvus server.")
        if self._collection is None:
            if utility.has_collection(COLLECTION_NAME_BASE):
                self._collection = Collection(COLLECTION_NAME_BASE)
            else:
                self.create_collection()
        return self._collection

    def insert(self, data: list[dict]) -> list[int]:
        """
        插入数据
        data: [{"file_name": "", "patent_id": "", "page_num": "", "file_path": "", "embedding": []}]
        """
        collection = self.get_collection()

        entities = [
            [d["file_name"] for d in data],
            [d["patent_id"] for d in data],
            [d["page_num"] for d in data],
            [d["file_path"] for d in data],
            [d["embedding"] for d in data],
            [int(time.time()) for _ in data],
        ]

        result = collection.insert(entities)
        collection.flush()
        return result.primary_keys

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        min_score: float = 0.5
    ) -> tuple[list[dict], float]:
        """
        搜索相似向量
        返回: (结果列表, 搜索耗时ms)
        """
        collection = self.get_collection()

        print(f"[MILVUS-BASE] Searching with top_k={top_k}, min_score={min_score}")
        start_time = time.time()
        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=SEARCH_PARAMS,
            limit=top_k * 2,  # 多取一些用于过滤
            output_fields=["file_name", "patent_id", "page_num", "file_path"]
        )
        search_time_ms = (time.time() - start_time) * 1000
        print(f"[MILVUS-BASE] Search completed in {search_time_ms:.1f}ms, found {len(results[0])} results")

        # 过滤和格式化结果
        filtered = []
        for hit in results[0]:
            if hit.score >= min_score:
                filtered.append({
                    "id": hit.id,
                    "score": float(hit.score),
                    "file_name": hit.entity.get("file_name"),
                    "patent_id": hit.entity.get("patent_id"),
                    "page_num": hit.entity.get("page_num"),
                    "file_path": hit.entity.get("file_path"),
                })

        print(f"[MILVUS-BASE] Filtered to {len(filtered)} results with score >= {min_score}")
        return filtered[:top_k], search_time_ms

    def get_stats(self) -> dict:
        """获取 Collection 统计信息"""
        if not self._connected:
            print(f"[MILVUS-BASE] Not connected, returning empty stats")
            return {
                "name": COLLECTION_NAME_BASE,
                "num_entities": 0,
                "has_index": False,
                "connected": False,
                "error": "Milvus not connected"
            }
        try:
            collection = self.get_collection()
            collection.flush()

            stats = {
                "name": COLLECTION_NAME_BASE,
                "num_entities": collection.num_entities,
                "has_index": collection.has_index(),
                "connected": True,
            }
            print(f"[MILVUS-BASE] Stats: {stats}")
            return stats
        except Exception as e:
            print(f"[MILVUS-BASE] Failed to get stats: {e}")
            return {
                "name": COLLECTION_NAME_BASE,
                "num_entities": 0,
                "has_index": False,
                "connected": False,
                "error": str(e)
            }

    def get_existing_files(self) -> set[str]:
        """获取已存在的文件名集合（用于断点续传）"""
        if not self._connected:
            print(f"[MILVUS-BASE] Not connected, returning empty file set")
            return set()

        collection = self.get_collection()
        collection.flush()

        num_entities = collection.num_entities
        print(f"[MILVUS-BASE] Collection has {num_entities} entities")

        if num_entities == 0:
            return set()

        # 查询所有 file_name
        print(f"[MILVUS-BASE] Querying existing file names...")
        results = collection.query(
            expr="id >= 0",
            output_fields=["file_name"],
            limit=num_entities
        )

        file_set = {r["file_name"] for r in results}
        print(f"[MILVUS-BASE] Found {len(file_set)} existing files")
        return file_set

    def drop_collection(self) -> bool:
        """删除 Collection（慎用）"""
        if utility.has_collection(COLLECTION_NAME_BASE):
            utility.drop_collection(COLLECTION_NAME_BASE)
            self._collection = None
            print(f"[MILVUS-BASE] Collection '{COLLECTION_NAME_BASE}' dropped")
            return True
        return False


# 单例实例
milvus_base_service = MilvusBaseService()
