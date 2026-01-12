"""
外观专利完整导入脚本
1. 上传图片到 MinIO
2. 解析 XML 元数据
3. DINOv2 向量化
4. 存入 Milvus (design_patents_full)
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymilvus import (
    connections, Collection, FieldSchema, CollectionSchema, DataType, utility
)
from app.config import (
    MILVUS_HOST, MILVUS_PORT, EMBEDDING_DIM_BASE,
    MINIO_ENDPOINT, MINIO_BUCKET, BATCH_SIZE
)
from app.services.minio_service import minio_service

# 从同目录导入
from design_patent_parser import parse_design_patent_xml, scan_design_patents

# Collection 配置
COLLECTION_NAME = "design_patents_full"
MINIO_PREFIX = "design_patents"

INDEX_PARAMS = {
    "index_type": "IVF_FLAT",
    "metric_type": "COSINE",
    "params": {"nlist": 128}
}


def connect_milvus():
    print(f"[MILVUS] Connecting to {MILVUS_HOST}:{MILVUS_PORT}...")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    print("[MILVUS] Connected")


def create_collection() -> Collection:
    """创建含完整元数据的 Collection"""
    print(f"[MILVUS] Checking collection '{COLLECTION_NAME}'...")

    if utility.has_collection(COLLECTION_NAME):
        print(f"[MILVUS] Collection exists, dropping...")
        utility.drop_collection(COLLECTION_NAME)

    print(f"[MILVUS] Creating collection '{COLLECTION_NAME}'...")
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        # 核心字段
        FieldSchema(name="patent_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="image_index", dtype=DataType.INT16),
        FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=512),  # MinIO URL
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM_BASE),
        # 元数据字段
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="loc_class", dtype=DataType.VARCHAR, max_length=20),
        FieldSchema(name="loc_edition", dtype=DataType.VARCHAR, max_length=10),
        FieldSchema(name="pub_date", dtype=DataType.INT64),
        FieldSchema(name="filing_date", dtype=DataType.INT64),
        FieldSchema(name="grant_term", dtype=DataType.INT16),
        FieldSchema(name="applicant_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="applicant_country", dtype=DataType.VARCHAR, max_length=10),
        FieldSchema(name="inventor_names", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="assignee_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="claim_text", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="image_count", dtype=DataType.INT16),
        FieldSchema(name="created_at", dtype=DataType.INT64),
    ]

    schema = CollectionSchema(fields, description="Design patents with full metadata")
    collection = Collection(name=COLLECTION_NAME, schema=schema)

    # 创建索引
    print("[MILVUS] Creating index...")
    collection.create_index(field_name="embedding", index_params=INDEX_PARAMS)
    print("[MILVUS] Index created")

    return collection


def upload_image_to_minio(local_path: str, patent_id: str, file_name: str) -> str:
    """上传图片到 MinIO，返回 URL"""
    object_name = f"{MINIO_PREFIX}/{patent_id}/{file_name}"

    if minio_service.file_exists(object_name):
        return minio_service.get_url(object_name)

    url = minio_service.upload_file(local_path, object_name)
    return url


def main():
    print("=" * 60)
    print("外观专利完整导入 (MinIO + Milvus)")
    print("=" * 60)

    # 数据目录
    data_dir = Path(__file__).parent.parent.parent
    print(f"[DATA] 数据目录: {data_dir}")

    # 连接服务
    connect_milvus()
    minio_service.connect()

    # 创建 Collection
    collection = create_collection()
    collection.load()

    # 扫描专利
    print("\n[SCAN] 扫描外观专利...")
    patents = scan_design_patents(str(data_dir))
    print(f"[SCAN] 共 {len(patents)} 个专利")

    if not patents:
        print("[ERROR] 未找到专利数据")
        return

    # 加载 DINOv2
    print("\n[MODEL] 加载 DINOv2 模型...")
    from app.services.dinov2_base_service import dinov2_base_extractor
    print("[MODEL] 模型加载完成")

    # 统计
    total_images = sum(p.image_count for p in patents)
    print(f"\n[IMPORT] 开始导入: {len(patents)} 专利, {total_images} 图片")

    success_count = 0
    fail_count = 0
    batch_data = []

    for patent_idx, patent in enumerate(patents):
        print(f"\n[{patent_idx + 1}/{len(patents)}] {patent.patent_id}: {patent.title[:30]}...")

        for img_idx, img_file in enumerate(patent.images):
            # 图片本地路径
            local_path = os.path.join(patent.data_dir, img_file)
            if not os.path.exists(local_path):
                print(f"  [SKIP] 图片不存在: {img_file}")
                fail_count += 1
                continue

            try:
                # 1. 上传 MinIO
                minio_url = upload_image_to_minio(local_path, patent.patent_id, img_file)
                if not minio_url:
                    print(f"  [FAIL] MinIO 上传失败: {img_file}")
                    fail_count += 1
                    continue

                # 2. 向量化
                embedding, _ = dinov2_base_extractor.extract_single(local_path)

                # 3. 准备数据
                batch_data.append({
                    "patent_id": patent.patent_id,
                    "image_index": img_idx,
                    "file_name": img_file,
                    "file_path": minio_url,
                    "embedding": embedding,
                    "title": patent.title[:500],
                    "loc_class": patent.loc_class,
                    "loc_edition": patent.loc_edition,
                    "pub_date": patent.pub_date,
                    "filing_date": patent.filing_date,
                    "grant_term": patent.grant_term,
                    "applicant_name": patent.applicant_name[:256],
                    "applicant_country": patent.applicant_country,
                    "inventor_names": patent.inventor_names[:500],
                    "assignee_name": patent.assignee_name[:256],
                    "claim_text": patent.claim_text[:500],
                    "image_count": patent.image_count,
                    "created_at": int(time.time()),
                })

                success_count += 1

                # 批量插入
                if len(batch_data) >= BATCH_SIZE:
                    insert_batch(collection, batch_data)
                    batch_data = []

            except Exception as e:
                print(f"  [ERROR] {img_file}: {e}")
                fail_count += 1

        # 每个专利后显示进度
        progress = (patent_idx + 1) / len(patents) * 100
        print(f"  进度: {progress:.1f}% | 成功: {success_count} | 失败: {fail_count}")

    # 插入剩余数据
    if batch_data:
        insert_batch(collection, batch_data)

    # 完成
    collection.flush()
    print("\n" + "=" * 60)
    print(f"导入完成!")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"Collection 总记录: {collection.num_entities}")
    print("=" * 60)


def insert_batch(collection: Collection, batch_data: list):
    """批量插入数据"""
    entities = [
        [d["patent_id"] for d in batch_data],
        [d["image_index"] for d in batch_data],
        [d["file_name"] for d in batch_data],
        [d["file_path"] for d in batch_data],
        [d["embedding"] for d in batch_data],
        [d["title"] for d in batch_data],
        [d["loc_class"] for d in batch_data],
        [d["loc_edition"] for d in batch_data],
        [d["pub_date"] for d in batch_data],
        [d["filing_date"] for d in batch_data],
        [d["grant_term"] for d in batch_data],
        [d["applicant_name"] for d in batch_data],
        [d["applicant_country"] for d in batch_data],
        [d["inventor_names"] for d in batch_data],
        [d["assignee_name"] for d in batch_data],
        [d["claim_text"] for d in batch_data],
        [d["image_count"] for d in batch_data],
        [d["created_at"] for d in batch_data],
    ]
    collection.insert(entities)
    print(f"  [INSERT] 插入 {len(batch_data)} 条记录")


if __name__ == "__main__":
    main()
