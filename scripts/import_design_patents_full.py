"""
外观专利完整导入脚本
1. 上传图片到 MinIO
2. 解析 XML 元数据
3. DINOv2 向量化
4. 存入 Milvus (design_patents_full)

优化说明:
- 使用生成器模式扫描专利，避免一次性加载所有数据到内存
- 定期清理 GPU 显存，防止显存泄漏
- 定期触发 Python GC，防止内存泄漏
"""
import os
import sys
import gc
import time
import logging
from pathlib import Path
from datetime import datetime

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
from design_patent_parser import parse_design_patent_xml, scan_all_design_patents

# Collection 配置
COLLECTION_NAME = "design_patents_full"
MINIO_PREFIX = "design_patents"
INSERT_BATCH_SIZE = 16  # 批量插入大小，增大以提高吞吐
MAX_VARCHAR_LEN = 4096  # VARCHAR 最大长度
GC_INTERVAL = 100  # 每处理 N 张图片后执行一次内存清理

INDEX_PARAMS = {
    "index_type": "IVF_FLAT",
    "metric_type": "COSINE",
    "params": {"nlist": 128}
}

# 日志配置
LOG_DIR = Path(__file__).parent
LOG_FILE = LOG_DIR / f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def connect_milvus():
    logger.info(f"连接 Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
    logger.info("Milvus 连接成功")


def create_collection() -> Collection:
    """创建含完整元数据的 Collection（扩大 VARCHAR 字段）"""
    logger.info(f"检查 collection '{COLLECTION_NAME}'...")

    if utility.has_collection(COLLECTION_NAME):
        logger.warning(f"Collection 已存在，将删除重建")
        utility.drop_collection(COLLECTION_NAME)

    logger.info(f"创建 collection '{COLLECTION_NAME}'...")
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="patent_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="image_index", dtype=DataType.INT16),
        FieldSchema(name="file_name", dtype=DataType.VARCHAR, max_length=1024),
        FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM_BASE),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LEN),
        FieldSchema(name="loc_class", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="loc_edition", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="pub_date", dtype=DataType.INT64),
        FieldSchema(name="filing_date", dtype=DataType.INT64),
        FieldSchema(name="grant_term", dtype=DataType.INT16),
        FieldSchema(name="applicant_name", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LEN),
        FieldSchema(name="applicant_country", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="inventor_names", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LEN),
        FieldSchema(name="assignee_name", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LEN),
        FieldSchema(name="claim_text", dtype=DataType.VARCHAR, max_length=MAX_VARCHAR_LEN),
        FieldSchema(name="image_count", dtype=DataType.INT16),
        FieldSchema(name="created_at", dtype=DataType.INT64),
    ]

    schema = CollectionSchema(fields, description="Design patents with full metadata")
    collection = Collection(name=COLLECTION_NAME, schema=schema)

    logger.info("创建索引...")
    collection.create_index(field_name="embedding", index_params=INDEX_PARAMS)
    logger.info("索引创建完成")

    return collection


def upload_image_to_minio(local_path: str, patent_id: str, file_name: str) -> str:
    """上传图片到 MinIO，返回 URL"""
    object_name = f"{MINIO_PREFIX}/{patent_id}/{file_name}"

    if minio_service.file_exists(object_name):
        return minio_service.get_url(object_name)

    url = minio_service.upload_file(local_path, object_name)
    return url


def format_time(seconds: float) -> str:
    """格式化时间显示"""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"



def get_existing_keys(collection: Collection) -> set:
    """获取已存在的 patent_id + file_name 组合（游标分页）"""
    existing = set()
    last_id = -1
    try:
        while True:
            results = collection.query(
                expr=f'id > {last_id}',
                output_fields=['id', 'patent_id', 'file_name'],
                limit=500
            )
            if not results:
                break
            for r in results:
                existing.add(f"{r['patent_id']}_{r['file_name']}")
            last_id = max(r['id'] for r in results)
        logger.info(f"已存在 {len(existing)} 条记录")
    except Exception as e:
        logger.error(f"查询已存在记录失败: {e}")
    return existing


def truncate_str(s, max_len: int) -> str:
    """安全截断字符串"""
    if s is None:
        return ""
    s = str(s)
    return s[:max_len] if len(s) > max_len else s

def clear_gpu_memory():
    """清理 GPU 显存，防止显存泄漏"""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
    except ImportError:
        pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description='外观专利完整导入')
    parser.add_argument('--data-dir', default=r'D:\data', help='数据根目录 (默认: D:\\data)')
    parser.add_argument('--append', action='store_true', help='追加模式，不删除现有数据')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("外观专利完整导入 (MinIO + Milvus)")
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info("=" * 60)

    # 数据目录
    data_dir = args.data_dir
    logger.info(f"数据目录: {data_dir}")

    # 连接服务
    connect_milvus()
    minio_service.connect()

    # 创建或获取 Collection
    if args.append and utility.has_collection(COLLECTION_NAME):
        logger.info(f"追加模式，使用现有 collection '{COLLECTION_NAME}'")
        collection = Collection(name=COLLECTION_NAME)
        existing_count = collection.num_entities
        logger.info(f"现有记录数: {existing_count}")
    else:
        collection = create_collection()
    collection.load()

    # 获取已存在的记录用于去重
    existing_keys = get_existing_keys(collection) if args.append else set()

    # 加载 DINOv2
    logger.info("加载 DINOv2 模型...")
    from app.services.dinov2_base_service import dinov2_base_extractor
    logger.info("模型加载完成")

    # 使用生成器模式扫描专利，避免一次性加载到内存
    logger.info("开始扫描外观专利 (生成器模式)...")
    patent_generator = scan_all_design_patents(data_dir)

    # 时间统计
    start_time = time.time()
    image_times = []

    success_count = 0
    fail_count = 0
    skip_count = 0
    batch_data = []
    processed_images = 0
    patent_count = 0
    failed_records = []  # 记录失败的详情

    # 遍历生成器，逐个处理专利
    for patent in patent_generator:
        patent_count += 1
        logger.info(f"[专利 {patent_count}] {patent.patent_id}: {patent.title[:30] if patent.title else 'N/A'}...")

        for img_idx, img_file in enumerate(patent.images):
            img_start_time = time.time()
            processed_images += 1

            # 检查是否已存在
            dedup_key = f"{patent.patent_id}_{img_file}"
            if dedup_key in existing_keys:
                logger.debug(f"  跳过已存在: {img_file}")
                skip_count += 1
                continue

            # 图片本地路径
            local_path = os.path.join(patent.data_dir, img_file)
            if not os.path.exists(local_path):
                logger.warning(f"  图片不存在: {img_file}")
                fail_count += 1
                failed_records.append(f"{patent.patent_id},{img_file},图片不存在")
                continue

            try:
                # 1. 上传 MinIO
                minio_url = upload_image_to_minio(local_path, patent.patent_id, img_file)
                if not minio_url:
                    logger.error(f"  MinIO 上传失败: {img_file}")
                    fail_count += 1
                    failed_records.append(f"{patent.patent_id},{img_file},MinIO上传失败")
                    continue

                # 2. 向量化
                embedding, extract_time = dinov2_base_extractor.extract_single(local_path)

                # 3. 准备数据（安全截断）
                batch_data.append({
                    "patent_id": truncate_str(patent.patent_id, 256),
                    "image_index": img_idx,
                    "file_name": truncate_str(img_file, 1024),
                    "file_path": truncate_str(minio_url, 2048),
                    "embedding": embedding,
                    "title": truncate_str(patent.title, MAX_VARCHAR_LEN),
                    "loc_class": truncate_str(patent.loc_class, 256),
                    "loc_edition": truncate_str(patent.loc_edition, 256),
                    "pub_date": patent.pub_date,
                    "filing_date": patent.filing_date,
                    "grant_term": patent.grant_term,
                    "applicant_name": truncate_str(patent.applicant_name, MAX_VARCHAR_LEN),
                    "applicant_country": truncate_str(patent.applicant_country, 256),
                    "inventor_names": truncate_str(patent.inventor_names, MAX_VARCHAR_LEN),
                    "assignee_name": truncate_str(patent.assignee_name, MAX_VARCHAR_LEN),
                    "claim_text": truncate_str(patent.claim_text, MAX_VARCHAR_LEN),
                    "image_count": patent.image_count,
                    "created_at": int(time.time()),
                })

                success_count += 1
                image_times.append(time.time() - img_start_time)

                # 批量插入
                if len(batch_data) >= INSERT_BATCH_SIZE:
                    insert_success = insert_batch(collection, batch_data)
                    if not insert_success:
                        for d in batch_data:
                            failed_records.append(f"{d['patent_id']},{d['file_name']},插入失败")
                    batch_data = []

                # 定期清理内存，防止泄漏
                if processed_images % GC_INTERVAL == 0:
                    clear_gpu_memory()
                    gc.collect()

            except Exception as e:
                logger.error(f"  处理失败 {img_file}: {e}")
                fail_count += 1
                failed_records.append(f"{patent.patent_id},{img_file},{str(e)[:100]}")

        # 进度显示 (生成器模式无法预知总数，只显示已处理数量)
        elapsed_total = time.time() - start_time
        if image_times and processed_images % 50 == 0:
            avg_time = sum(image_times[-100:]) / len(image_times[-100:])  # 用最近100条计算平均
            logger.info(f"  进度: 已处理 {processed_images} 张 | 成功: {success_count} | 跳过: {skip_count} | 失败: {fail_count}")
            logger.info(f"  已用: {format_time(elapsed_total)} | 平均: {avg_time:.2f}秒/张")

    # 插入剩余数据
    if batch_data:
        insert_success = insert_batch(collection, batch_data)
        if not insert_success:
            for d in batch_data:
                failed_records.append(f"{d['patent_id']},{d['file_name']},插入失败")

    # 保存失败记录
    if failed_records:
        fail_file = LOG_DIR / f"failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(fail_file, 'w', encoding='utf-8') as f:
            f.write("patent_id,file_name,error\n")
            f.write('\n'.join(failed_records))
        logger.info(f"失败记录已保存: {fail_file}")

    # 完成
    collection.flush()
    total_time = time.time() - start_time

    logger.info("=" * 60)
    logger.info("导入完成!")
    logger.info(f"成功: {success_count}")
    logger.info(f"跳过: {skip_count}")
    logger.info(f"失败: {fail_count}")
    logger.info(f"Collection 总记录: {collection.num_entities}")
    logger.info(f"总耗时: {format_time(total_time)}")
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info("=" * 60)


def insert_batch(collection: Collection, batch_data: list) -> bool:
    """批量插入数据，失败时尝试逐条插入"""
    try:
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
        logger.info(f"  插入 {len(batch_data)} 条记录")
        return True
    except Exception as e:
        logger.error(f"批量插入失败 ({len(batch_data)} 条): {e}")
        # 尝试逐条插入
        success = 0
        for d in batch_data:
            try:
                single = [[v] for v in [
                    d["patent_id"], d["image_index"], d["file_name"], d["file_path"],
                    d["embedding"], d["title"], d["loc_class"], d["loc_edition"],
                    d["pub_date"], d["filing_date"], d["grant_term"], d["applicant_name"],
                    d["applicant_country"], d["inventor_names"], d["assignee_name"],
                    d["claim_text"], d["image_count"], d["created_at"]
                ]]
                collection.insert(single)
                success += 1
            except Exception as e2:
                logger.error(f"单条插入失败 ({d['patent_id']}_{d['file_name']}): {e2}")
        logger.info(f"  逐条插入: {success}/{len(batch_data)} 成功")
        return success == len(batch_data)


if __name__ == "__main__":
    main()
