"""导入睿观图片到 Milvus (独立 collection)"""
import os
import sys
import time

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymilvus import (
    connections,
    Collection,
    FieldSchema,
    CollectionSchema,
    DataType,
    utility
)

from app.config import (
    MILVUS_HOST,
    MILVUS_PORT,
    COLLECTION_NAME_RUIGUAN,
    EMBEDDING_DIM_BASE,
    INDEX_PARAMS,
    SUPPORTED_IMAGE_FORMATS,
    BATCH_SIZE,
    MINIO_ENDPOINT,
    MINIO_BUCKET
)
from app.services.minio_service import minio_service

# 配置
LOCAL_DIR = "睿观"
MINIO_PREFIX = "ruiguan"


def connect_milvus():
    """连接 Milvus"""
    print(f"[MILVUS] Connecting to {MILVUS_HOST}:{MILVUS_PORT}...")
    connections.connect(
        alias="default",
        host=MILVUS_HOST,
        port=MILVUS_PORT
    )
    print("[MILVUS] Connected")


def create_collection() -> Collection:
    """创建睿观 collection"""
    print(f"[MILVUS] Checking collection '{COLLECTION_NAME_RUIGUAN}'...")

    if utility.has_collection(COLLECTION_NAME_RUIGUAN):
        print(f"[MILVUS] Collection '{COLLECTION_NAME_RUIGUAN}' already exists")
        return Collection(COLLECTION_NAME_RUIGUAN)

    print(f"[MILVUS] Creating collection '{COLLECTION_NAME_RUIGUAN}'...")
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="patent_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="page_num", dtype=DataType.VARCHAR, max_length=16),
        FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM_BASE),
        FieldSchema(name="created_at", dtype=DataType.INT64),
    ]

    schema = CollectionSchema(fields, description="Ruiguan image embeddings (Base model)")
    collection = Collection(name=COLLECTION_NAME_RUIGUAN, schema=schema)
    print(f"[MILVUS] Collection '{COLLECTION_NAME_RUIGUAN}' created")

    # 创建索引
    print(f"[MILVUS] Creating index...")
    collection.create_index(field_name="embedding", index_params=INDEX_PARAMS)
    print("[MILVUS] Index created")

    return collection


def get_existing_files(collection: Collection) -> set:
    """获取已存在的文件名"""
    collection.flush()
    num = collection.num_entities
    print(f"[MILVUS] Collection has {num} entities")

    if num == 0:
        return set()

    results = collection.query(
        expr="id >= 0",
        output_fields=["file_name"],
        limit=num
    )
    return {r["file_name"] for r in results}


def scan_images() -> list:
    """扫描本地图片"""
    images = []
    for filename in os.listdir(LOCAL_DIR):
        ext = os.path.splitext(filename)[1].lower()
        if ext in SUPPORTED_IMAGE_FORMATS:
            images.append(filename)
    return sorted(images)


def parse_filename(filename: str) -> dict:
    """解析文件名"""
    name, _ = os.path.splitext(filename)
    return {
        "patent_id": name,
        "date": "",
        "page_num": "001",
    }


def main():
    print("[RUIGUAN] ========== Import 睿观 to Milvus ==========")

    # 连接 Milvus
    connect_milvus()

    # 创建 collection
    collection = create_collection()

    # 加载 collection
    print("[MILVUS] Loading collection...")
    collection.load()
    print("[MILVUS] Collection loaded")

    # 获取已存在的文件
    existing = get_existing_files(collection)
    print(f"[RUIGUAN] Existing files: {len(existing)}")

    # 扫描图片
    all_images = scan_images()
    print(f"[RUIGUAN] Total images: {len(all_images)}")

    # 过滤已存在的
    pending = [img for img in all_images if img not in existing]
    print(f"[RUIGUAN] Pending: {len(pending)}")

    if not pending:
        print("[RUIGUAN] All images already imported!")
        return

    # 延迟导入 DINOv2
    print("[RUIGUAN] Loading DINOv2 model...")
    from app.services.dinov2_base_service import dinov2_base_extractor
    print("[RUIGUAN] Model loaded")

    # 分批处理
    total_batches = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    success_count = 0
    fail_count = 0

    for batch_idx, i in enumerate(range(0, len(pending), BATCH_SIZE)):
        batch_files = pending[i:i + BATCH_SIZE]
        batch_paths = [os.path.join(LOCAL_DIR, f) for f in batch_files]

        print(f"[BATCH {batch_idx + 1}/{total_batches}] Processing {len(batch_files)} images...")

        # 提取特征
        try:
            embeddings, extract_time = dinov2_base_extractor.extract_batch(batch_paths)
            print(f"[BATCH {batch_idx + 1}] Features extracted in {extract_time:.1f}ms")
        except Exception as e:
            print(f"[BATCH {batch_idx + 1}] Batch extraction failed: {e}")
            embeddings = []
            for path in batch_paths:
                try:
                    emb, _ = dinov2_base_extractor.extract_single(path)
                    embeddings.append(emb)
                except Exception as e2:
                    print(f"[BATCH {batch_idx + 1}] Failed: {os.path.basename(path)}: {e2}")
                    embeddings.append(None)
                    fail_count += 1

        # 准备数据
        insert_data = []
        for filename, embedding in zip(batch_files, embeddings):
            if embedding is None:
                continue

            parsed = parse_filename(filename)

            # MinIO URL
            minio_url = f"http://{MINIO_ENDPOINT}/{MINIO_BUCKET}/{MINIO_PREFIX}/{filename}"

            insert_data.append({
                "file_name": filename,
                "patent_id": parsed["patent_id"],
                "page_num": parsed["page_num"],
                "file_path": minio_url,
                "embedding": embedding,
            })

        # 插入 Milvus
        if insert_data:
            try:
                entities = [
                    [d["file_name"] for d in insert_data],
                    [d["patent_id"] for d in insert_data],
                    [d["page_num"] for d in insert_data],
                    [d["file_path"] for d in insert_data],
                    [d["embedding"] for d in insert_data],
                    [int(time.time()) for _ in insert_data],
                ]
                collection.insert(entities)
                collection.flush()
                success_count += len(insert_data)
                print(f"[BATCH {batch_idx + 1}] Inserted {len(insert_data)} records")
            except Exception as e:
                print(f"[BATCH {batch_idx + 1}] Insert failed: {e}")
                fail_count += len(insert_data)

        progress = (i + len(batch_files)) / len(pending) * 100
        print(f"[PROGRESS] {i + len(batch_files)}/{len(pending)} ({progress:.1f}%)")

    print("[RUIGUAN] ========== Import completed ==========")
    print(f"[RUIGUAN] Success: {success_count}, Failed: {fail_count}")
    print(f"[RUIGUAN] Total in collection: {collection.num_entities}")


if __name__ == "__main__":
    main()
