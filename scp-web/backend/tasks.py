# backend/tasks.py
import os
import uuid
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from config import TEMP_IMAGES_FOLDER
from database import (
    IMAGE_TYPE_ENCRYPTED,
    save_image_record, save_analysis_record,
    get_db, COLLECTION_ANALYSIS,
)
from core_logic.arnold_encryption import ArnoldEncryption
from core_logic.xor_encryption import XOREncryption
from core_logic.xxtea_encryption import XXTEAEncryption
from core_logic.aes_encryption import AESEncryption, AES_AVAILABLE
from core_logic.logistic_chaotic_encryption import LogisticChaoticEncryption
from core_logic.aesgcm_encryption import AESGCMEncryption
from core_logic.chacha20_encryption import ChaCha20Encryption
from core_logic.rsa_hybrid_encryption import RSAHybridEncryption
from core_logic.statistical_analysis import StatisticalAnalysis
from core_logic.utils import load_image_safe, save_image_safe, image_to_base64

logger = logging.getLogger(__name__)

ALL_ALGORITHMS = [
    {"name": "Arnold变换",      "params": {"iterations": 10}},
    {"name": "XOR加密",         "params": {"key": "batch_xor_key", "xor_mode": "string"}},
    {"name": "XXTEA加密",       "params": {"key": "batch_xxtea_key"}},
    {"name": "AES加密",         "params": {"key": "batch_aes_key_123", "mode": "CFB"}},
    {"name": "Logistic混沌加密","params": {"key_string": "batch_logistic_key",
                                           "use_key_params": True, "r": 3.99, "x0": 0.01,
                                           "discard_iterations": 100}},
    {"name": "AES-GCM加密",     "params": {"key_string": "batch_aesgcm_key"}},
    {"name": "ChaCha20加密",    "params": {"key_string": "batch_chacha20_key"}},
    {"name": "RSA混合加密",     "params": {"key_string": "batch_rsa_hybrid_key"}},
]


def _analysis_exists(original_image_id: str, algorithm_name: str) -> bool:
    """
    检查 (original_image_id, algorithm) 组合是否已有分析记录。
    这是增量模式的核心判断，在任务函数体内调用，直接查 MongoDB。

    为什么在后端做而不是前端做：
      前端通过 /api/dashboard/recent 预过滤时，
      受限于 limit 参数和算法不同的缺失集合，
      前端无法准确构造「哪张图缺哪个算法」的精确列表，
      容易出现漏过滤（重复处理）或过度过滤（跳过应处理的）的问题。
      后端直接查 MongoDB，100% 准确。
    """
    try:
        db  = get_db()
        doc = db[COLLECTION_ANALYSIS].find_one(
            {
                "original_image_id": original_image_id,
                "algorithm":         algorithm_name,
            },
            {"_id": 1}   # 只取 _id，减少传输量
        )
        return doc is not None
    except Exception as e:
        # 查询失败时保守处理：返回 False，继续执行（宁可重复也不漏）
        logger.warning(f"[incremental check] 查询失败，跳过检查: {e}")
        return False


def _build_encryptor(algorithm_name: str, params: dict):
    if algorithm_name == "Arnold变换":
        return ArnoldEncryption()
    elif algorithm_name == "XOR加密":
        return XOREncryption(
            key_string=params.get('key', 'default_key'),
            xor_mode=params.get('xor_mode', 'string'),
            xor_byte=params.get('xor_byte', 0x17),
        )
    elif algorithm_name == "XXTEA加密":
        return XXTEAEncryption(key_string=params.get('key', 'default_key'))
    elif algorithm_name == "AES加密":
        if not AES_AVAILABLE:
            raise ImportError("PyCryptodome 未安装")
        return AESEncryption(
            key=params.get('key', 'default_aes_key'),
            mode=params.get('mode', 'CFB')
        )
    elif algorithm_name == "Logistic混沌加密":
        return LogisticChaoticEncryption(
            key_string=params.get('key_string', 'default_logistic_key'),
            r=params.get('r', 3.99), x0=params.get('x0', 0.01),
            discard_iterations=params.get('discard_iterations', 100),
        )
    elif algorithm_name == "AES-GCM加密":
        return AESGCMEncryption(
            key_string=params.get('key_string', 'default_aesgcm_key')
        )
    elif algorithm_name == "ChaCha20加密":
        return ChaCha20Encryption(
            key_string=params.get('key_string', 'default_chacha20_key')
        )
    elif algorithm_name == "RSA混合加密":
        return RSAHybridEncryption(
            key_string=params.get('key_string', 'default_rsa_key')
        )
    else:
        raise ValueError(f"不支持的算法: {algorithm_name}")


def _do_encrypt(encryptor, image, algorithm_name, params):
    if algorithm_name == "Arnold变换":
        return encryptor.encrypt(image, params.get('iterations', 10))
    elif algorithm_name == "XXTEA加密":
        return encryptor.encrypt_image(image)
    elif algorithm_name == "Logistic混沌加密":
        return encryptor.encrypt(image, use_key_params=params.get('use_key_params', True))
    else:
        return encryptor.encrypt(image)


def _run_single_encrypt_analyze(
    original_image: np.ndarray,
    original_image_id: str,
    original_filename: str,
    algorithm_name: str,
    params: dict,
    incremental: bool = True,    # ← 新增参数，默认开启增量检查
) -> dict:
    """
    对单张图像执行一种算法的加密 + 统计分析，并写入 MongoDB。

    incremental=True 时：
      执行前先检查 MongoDB 是否已有该 (image_id, algorithm) 的分析记录。
      如果已有，直接返回 skipped=True，不重复处理。
    """
    result = {
        "algorithm":              algorithm_name,
        "original_image_id":      original_image_id,
        "original_filename":      original_filename,
        "success":                False,
        "skipped":                False,   # ← 新增：标记是否因增量模式跳过
        "error":                  None,
        "encrypt_time_ms":        0,
        "security_score":         0,
        "metrics":                {},
        "encrypted_image_id":     None,
        "encrypted_image_base64": None,
        "encrypted_shape":        None,
    }

    # ── ★ 增量检查：已有记录就跳过，不重复处理 ──────────────
    if incremental and _analysis_exists(original_image_id, algorithm_name):
        result["skipped"] = True
        result["success"] = True   # 视为成功（不算失败）
        logger.info(
            f"[batch][skip] {original_filename} × {algorithm_name} 已有记录，跳过"
        )
        return result

    try:
        encryptor = _build_encryptor(algorithm_name, params)

        t0 = time.perf_counter()
        encrypted_image = _do_encrypt(encryptor, original_image, algorithm_name, params)
        encrypt_time_ms = round((time.perf_counter() - t0) * 1000, 2)

        enc_id   = str(uuid.uuid4())
        enc_path = os.path.join(TEMP_IMAGES_FOLDER, f"{enc_id}.png")
        save_image_safe(encrypted_image, enc_path)

        save_image_record(enc_id, {
            "image_type":        IMAGE_TYPE_ENCRYPTED,
            "path":              enc_path,
            "shape":             list(encrypted_image.shape),
            "original_image_id": original_image_id,
            "algorithm":         algorithm_name,
            "params":            params,
            "original_filename": original_filename,
            "from_batch":        True,
        })

        analyzer    = StatisticalAnalysis()
        metrics_raw = analyzer.analyze_security(original_image, encrypted_image)
        metrics     = _convert_numpy({
            k: v for k, v in metrics_raw.items()
            if k not in ('histogram_original', 'histogram_encrypted')
        })
        score = metrics.get('security_score', 0)

        save_analysis_record({
            "algorithm":           algorithm_name,
            "original_image_id":   original_image_id,
            "encrypted_image_id":  enc_id,
            "original_filename":   original_filename,
            "image_shape":         list(original_image.shape),
            "security_score":      score,
            "encrypt_time_ms":     encrypt_time_ms,
            "from_batch":          True,
            "metrics":             metrics,
            "histogram_original":  _convert_numpy(
                metrics_raw.get('histogram_original', {})
            ),
            "histogram_encrypted": _convert_numpy(
                metrics_raw.get('histogram_encrypted', {})
            ),
        })

        result.update({
            "success":                True,
            "encrypt_time_ms":        encrypt_time_ms,
            "security_score":         score,
            "metrics":                metrics,
            "encrypted_image_id":     enc_id,
            "encrypted_image_base64": image_to_base64(encrypted_image),
            "encrypted_shape":        list(encrypted_image.shape),
        })
        logger.info(
            f"[batch] {original_filename} × {algorithm_name} "
            f"score={score} t={encrypt_time_ms}ms"
        )

    except Exception as e:
        result["error"] = str(e)
        logger.error(
            f"[batch] {original_filename} × {algorithm_name} failed: {e}",
            exc_info=True
        )

    return result


def run_batch(
    image_records: list,
    selected_algorithms: list = None,
    max_workers: int = 4,
    incremental: bool = True,    # ← 新增：同步降级模式也支持增量
) -> dict:
    algorithms = selected_algorithms if selected_algorithms else ALL_ALGORITHMS
    tasks = []
    for rec in image_records:
        img = load_image_safe(rec['path'])
        if img is None:
            logger.warning(f"无法加载: {rec['path']}")
            continue
        for algo in algorithms:
            tasks.append((
                img, rec['image_id'], rec['filename'],
                algo['name'], algo['params']
            ))

    all_results   = []
    success_count = 0
    failed_count  = 0
    skipped_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_single_encrypt_analyze,
                img, iid, fname, aname, aparams,
                incremental   # 传递增量参数
            ): None
            for img, iid, fname, aname, aparams in tasks
        }
        for future in as_completed(futures):
            res = future.result()
            all_results.append(res)
            if res.get('skipped'):
                skipped_count += 1
            elif res['success']:
                success_count += 1
            else:
                failed_count += 1

    if skipped_count > 0:
        logger.info(f"[batch] 增量模式跳过 {skipped_count} 个已有记录")

    return {
        "total":   len(tasks),
        "success": success_count,
        "failed":  failed_count,
        "skipped": skipped_count,
        "results": all_results,
        "summary": _build_summary(all_results),
    }


def _build_summary(results: list) -> list:
    from collections import defaultdict
    groups = defaultdict(list)
    for r in results:
        # 跳过的记录不参与汇总统计
        if r['success'] and not r.get('skipped'):
            groups[r['algorithm']].append(r)
    summary = []
    for algo_name, items in groups.items():
        n = len(items)
        summary.append({
            "algorithm":   algo_name,
            "count":       n,
            "avg_score":   round(sum(i['security_score']   for i in items) / n, 2),
            "avg_time_ms": round(sum(i['encrypt_time_ms']  for i in items) / n, 2),
            "avg_entropy": round(sum(i['metrics'].get('entropy_encrypted', 0) for i in items) / n, 4),
            "avg_npcr":    round(sum(i['metrics'].get('npcr',  0) for i in items) / n, 4),
            "avg_uaci":    round(sum(i['metrics'].get('uaci',  0) for i in items) / n, 4),
        })
    summary.sort(key=lambda x: x['avg_score'], reverse=True)
    return summary


def _convert_numpy(obj):
    if isinstance(obj, np.integer):  return int(obj)
    if isinstance(obj, np.floating): return float(obj)
    if isinstance(obj, np.ndarray):  return obj.flatten().tolist()
    if isinstance(obj, dict):  return {k: _convert_numpy(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [_convert_numpy(i) for i in obj]
    return obj