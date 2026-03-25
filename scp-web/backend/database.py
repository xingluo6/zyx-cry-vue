# backend/database.py
import logging
from datetime import datetime
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from config import MONGO_URI, MONGO_DB_NAME, COLLECTION_IMAGES, COLLECTION_ANALYSIS

logger = logging.getLogger(__name__)

IMAGE_TYPE_ORIGINAL  = 'original'
IMAGE_TYPE_ENCRYPTED = 'encrypted'
IMAGE_TYPE_DECRYPTED = 'decrypted'

_client = None
_db     = None


def get_db():
    global _client, _db
    if _db is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
            _client.admin.command('ping')
            _db = _client[MONGO_DB_NAME]
            logger.info(f"MongoDB 连接成功: {MONGO_URI}, 数据库: {MONGO_DB_NAME}")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"MongoDB 连接失败: {e}")
            raise
    return _db


def close_db():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db     = None


def save_image_record(image_id: str, record: dict):
    db = get_db()
    record['_id']        = image_id
    record['created_at'] = datetime.utcnow()
    if 'image_type' not in record:
        record['image_type'] = (
            IMAGE_TYPE_ORIGINAL if 'original_image_id' not in record
            else IMAGE_TYPE_ENCRYPTED
        )
    db[COLLECTION_IMAGES].replace_one({'_id': image_id}, record, upsert=True)


def get_image_record(image_id: str):
    return get_db()[COLLECTION_IMAGES].find_one({'_id': image_id})


def image_exists(image_id: str) -> bool:
    return get_db()[COLLECTION_IMAGES].count_documents({'_id': image_id}, limit=1) > 0


def find_image_by_hash(file_hash: str, file_size: int = None):
    db    = get_db()
    query = {'file_hash': file_hash, 'image_type': IMAGE_TYPE_ORIGINAL}
    if file_size is not None:
        query['file_size'] = file_size
    return db[COLLECTION_IMAGES].find_one(query, {'_id': 1, 'original_filename': 1, 'shape': 1})


def get_image_library(page: int = 1, page_size: int = 24) -> dict:
    db    = get_db()
    query = {'$or': [
        {'image_type': IMAGE_TYPE_ORIGINAL},
        {'image_type': {'$exists': False}, 'original_image_id': {'$exists': False}},
    ]}
    total  = db[COLLECTION_IMAGES].count_documents(query)
    cursor = db[COLLECTION_IMAGES].find(
        query, {'_id': 1, 'original_filename': 1, 'shape': 1, 'created_at': 1}
    ).sort('created_at', DESCENDING).skip((page-1)*page_size).limit(page_size)
    items = []
    for doc in cursor:
        items.append({
            'image_id':   doc['_id'],
            'filename':   doc.get('original_filename', ''),
            'shape':      doc.get('shape', []),
            'created_at': doc['created_at'].strftime('%Y-%m-%d %H:%M:%S') if doc.get('created_at') else '',
        })
    return {'total': total, 'page': page, 'page_size': page_size,
            'pages': max(1, (total+page_size-1)//page_size), 'items': items}


def get_image_library_all_ids() -> list:
    db    = get_db()
    query = {'$or': [
        {'image_type': IMAGE_TYPE_ORIGINAL},
        {'image_type': {'$exists': False}, 'original_image_id': {'$exists': False}},
    ]}
    return [doc['_id'] for doc in db[COLLECTION_IMAGES].find(query, {'_id': 1})]


def delete_image_and_derivatives(image_id: str) -> dict:
    db          = get_db()
    deleted_ids = [image_id]
    derivatives = list(db[COLLECTION_IMAGES].find({'original_image_id': image_id}, {'_id': 1, 'path': 1}))
    for d in derivatives: deleted_ids.append(d['_id'])
    db[COLLECTION_IMAGES].delete_many({'_id': {'$in': deleted_ids}})
    orig      = db[COLLECTION_IMAGES].find_one({'_id': image_id}, {'path': 1})
    all_paths = ([orig['path']] if orig and orig.get('path') else []) + [d.get('path','') for d in derivatives]
    return {'deleted_ids': deleted_ids, 'count': len(deleted_ids), 'paths': all_paths}


def clean_intermediate_files() -> dict:
    """只清理中间产物记录，不删除 analysis 记录"""
    db            = get_db()
    intermediates = list(db[COLLECTION_IMAGES].find(
        {'image_type': {'$in': [IMAGE_TYPE_ENCRYPTED, IMAGE_TYPE_DECRYPTED]}},
        {'_id': 1, 'path': 1}
    ))
    paths  = [d.get('path', '') for d in intermediates]
    r_img  = db[COLLECTION_IMAGES].delete_many(
        {'image_type': {'$in': [IMAGE_TYPE_ENCRYPTED, IMAGE_TYPE_DECRYPTED]}}
    )
    logger.info(f"[clean_intermediate] 清理 {r_img.deleted_count} 条，analysis 保留")
    return {'deleted_images': r_img.deleted_count, 'paths': paths}


def save_analysis_record(record: dict) -> str:
    db = get_db()
    record['created_at'] = datetime.utcnow()
    return str(db[COLLECTION_ANALYSIS].insert_one(record).inserted_id)


def get_recent_analysis(limit: int = 20) -> list:
    db     = get_db()
    cursor = db[COLLECTION_ANALYSIS].find(
        {}, {'_id':1,'algorithm':1,'original_filename':1,'security_score':1,'metrics':1,'created_at':1}
    ).sort('created_at', DESCENDING).limit(limit)
    records = []
    for doc in cursor:
        doc['_id'] = str(doc['_id'])
        records.append(doc)
    return records


def delete_analysis_records(start_date=None, end_date=None, algorithm=None) -> dict:
    db    = get_db()
    query = {}
    df    = {}
    if start_date:
        try: df['$gte'] = datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError: pass
    if end_date:
        try: df['$lte'] = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23,minute=59,second=59)
        except ValueError: pass
    if df: query['created_at'] = df
    if algorithm: query['algorithm'] = algorithm
    result = db[COLLECTION_ANALYSIS].delete_many(query)
    return {'deleted_count': result.deleted_count,
            'filter': {'start_date': start_date, 'end_date': end_date, 'algorithm': algorithm}}


def get_analysis_date_range() -> dict:
    db       = get_db()
    earliest = db[COLLECTION_ANALYSIS].find_one({}, sort=[('created_at', 1)])
    latest   = db[COLLECTION_ANALYSIS].find_one({}, sort=[('created_at', DESCENDING)])
    return {
        'earliest': earliest['created_at'].strftime('%Y-%m-%d') if earliest and earliest.get('created_at') else None,
        'latest':   latest['created_at'].strftime('%Y-%m-%d')   if latest   and latest.get('created_at')   else None,
    }


def get_algorithm_stats() -> list:
    db       = get_db()
    pipeline = [
        {'$group': {
            '_id': '$algorithm', 'count': {'$sum': 1},
            'avg_score':   {'$avg': '$security_score'},
            'avg_entropy': {'$avg': '$metrics.entropy_encrypted'},
            'avg_npcr':    {'$avg': '$metrics.npcr'},
            'avg_uaci':    {'$avg': '$metrics.uaci'},
            'avg_psnr':    {'$avg': '$metrics.psnr'},
        }},
        {'$sort': {'avg_score': DESCENDING}},
    ]
    return [{'algorithm': d['_id'], 'count': d['count'],
             'avg_score': round(d.get('avg_score') or 0, 2),
             'avg_entropy': round(d.get('avg_entropy') or 0, 4),
             'avg_npcr': round(d.get('avg_npcr') or 0, 4),
             'avg_uaci': round(d.get('avg_uaci') or 0, 4),
             'avg_psnr': round(d.get('avg_psnr') or 0, 2)}
            for d in db[COLLECTION_ANALYSIS].aggregate(pipeline)]


def get_score_trend(limit: int = 50) -> list:
    db     = get_db()
    cursor = db[COLLECTION_ANALYSIS].find(
        {}, {'algorithm':1,'security_score':1,'created_at':1}
    ).sort('created_at', DESCENDING).limit(limit)
    records = [{'_id': str(d['_id']), 'algorithm': d.get('algorithm','未知'),
                'score': d.get('security_score', 0),
                'created_at': d['created_at'].strftime('%Y-%m-%d %H:%M:%S') if d.get('created_at') else ''}
               for d in cursor]
    records.reverse()
    return records


def get_total_counts() -> dict:
    db    = get_db()
    query = {'$or': [
        {'image_type': IMAGE_TYPE_ORIGINAL},
        {'image_type': {'$exists': False}, 'original_image_id': {'$exists': False}},
    ]}
    return {
        'image_count':    db[COLLECTION_IMAGES].count_documents(query),
        'analysis_count': db[COLLECTION_ANALYSIS].count_documents({}),
        'algo_count':     len(db[COLLECTION_ANALYSIS].distinct('algorithm')),
    }


def get_all_analysis_for_training() -> list:
    records = []
    for doc in get_db()[COLLECTION_ANALYSIS].find({}):
        doc['_id'] = str(doc['_id'])
        records.append(doc)
    return records


# ──────────────────────────────────────────────
# 🆕 实验对比聚合
# ──────────────────────────────────────────────

def get_experiment_stats(image_ids: list = None, algorithm_names: list = None) -> list:
    """
    按算法聚合计算各指标的均值和标准差，用于实验对比表格。

    参数：
        image_ids:       限定参与实验的原始图像 id 列表（None = 使用全部）
        algorithm_names: 限定算法列表（None = 使用全部）

    返回（每个算法一条）：
    [
        {
            "algorithm": "AES加密",
            "count": 15,
            "metrics": {
                "entropy_encrypted": {"mean": 7.99, "std": 0.01},
                "npcr":              {"mean": 99.97, "std": 0.02},
                "uaci":              {"mean": 33.45, "std": 0.12},
                "psnr":              {"mean": 8.13,  "std": 0.5},
                "security_score":    {"mean": 88.2,  "std": 2.1},
                "encrypt_time_ms":   {"mean": 12.3,  "std": 1.2},
                "correlation_h_encrypted": {"mean": 0.001, "std": 0.003},
                "correlation_v_encrypted": {"mean": 0.002, "std": 0.004},
                "correlation_d_encrypted": {"mean": 0.001, "std": 0.002},
                "chi2_encrypted":    {"mean": 320.1, "std": 45.2},
                "arl_encrypted":     {"mean": 1.52,  "std": 0.08},
            }
        },
        ...
    ]
    """
    db    = get_db()
    query = {}

    if image_ids:
        query['original_image_id'] = {'$in': image_ids}
    if algorithm_names:
        query['algorithm'] = {'$in': algorithm_names}

    # 获取原始记录（MongoDB $stdDevSamp 需要 4.0+，我们用 Python 计算）
    cursor = db[COLLECTION_ANALYSIS].find(query, {
        'algorithm': 1, 'security_score': 1, 'encrypt_time_ms': 1,
        'metrics.entropy_encrypted': 1,
        'metrics.npcr': 1, 'metrics.uaci': 1, 'metrics.psnr': 1,
        'metrics.correlation_h_encrypted': 1,
        'metrics.correlation_v_encrypted': 1,
        'metrics.correlation_d_encrypted': 1,
        'metrics.chi2_encrypted': 1,
        'metrics.arl_encrypted': 1,
    })

    from collections import defaultdict
    import math

    groups = defaultdict(list)
    for doc in cursor:
        algo = doc.get('algorithm', '')
        if not algo: continue
        m = doc.get('metrics', {})
        groups[algo].append({
            'security_score':          doc.get('security_score', 0),
            'encrypt_time_ms':         doc.get('encrypt_time_ms', 0),
            'entropy_encrypted':       m.get('entropy_encrypted', 0),
            'npcr':                    m.get('npcr', 0),
            'uaci':                    m.get('uaci', 0),
            'psnr':                    m.get('psnr', 0),
            'correlation_h_encrypted': m.get('correlation_h_encrypted', 0),
            'correlation_v_encrypted': m.get('correlation_v_encrypted', 0),
            'correlation_d_encrypted': m.get('correlation_d_encrypted', 0),
            'chi2_encrypted':          m.get('chi2_encrypted', 0),
            'arl_encrypted':           m.get('arl_encrypted', 0),
        })

    def mean_std(values):
        if not values: return {"mean": 0, "std": 0}
        n    = len(values)
        mean = sum(values) / n
        if n < 2:
            return {"mean": round(mean, 4), "std": 0}
        variance = sum((v - mean) ** 2 for v in values) / (n - 1)
        return {"mean": round(mean, 4), "std": round(math.sqrt(variance), 4)}

    metric_keys = [
        'entropy_encrypted', 'npcr', 'uaci', 'psnr',
        'security_score', 'encrypt_time_ms',
        'correlation_h_encrypted', 'correlation_v_encrypted',
        'correlation_d_encrypted', 'chi2_encrypted', 'arl_encrypted',
    ]

    results = []
    for algo, records in groups.items():
        metrics = {}
        for key in metric_keys:
            vals = [r[key] for r in records if r[key] is not None]
            metrics[key] = mean_std(vals)
        results.append({
            'algorithm': algo,
            'count':     len(records),
            'metrics':   metrics,
        })

    # 按安全评分均值降序
    results.sort(key=lambda x: x['metrics'].get('security_score', {}).get('mean', 0), reverse=True)
    return results
