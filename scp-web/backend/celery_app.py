# backend/celery_app.py
"""
Celery 配置与异步任务定义。

启动方式（必须在 backend/ 目录下运行）：
  cd backend
  celery -A celery_app worker --loglevel=info --concurrency=4
"""
import os
import sys
import logging

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from celery import Celery
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

celery_app = Celery(
    'image_crypto',
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer            = 'json',
    result_serializer          = 'json',
    accept_content             = ['json'],
    result_expires             = 3600,
    task_track_started         = True,
    worker_prefetch_multiplier = 1,
    task_acks_late             = True,
)


@celery_app.task(bind=True, name='batch_process_task')
def batch_process_task(
    self,
    image_records: list,
    selected_algorithms: list,
    max_workers: int = 4,
    incremental: bool = True,    # ★ 新增：是否启用增量跳过
):
    """
    异步批量处理任务。

    ★ 修复说明（BackendStoreError: value too large for Redis backend）：
      原版本把每条加密结果（含 base64 图像、直方图数组）全部放进返回值，
      几十张图 × 8 种算法累积后体积可能达到数十 MB，超过 Redis 单 key 上限。

      修复方案：
        ① 任务返回值只保留轻量的「汇总统计」（summary + 计数），不含大体积字段
        ② 每条分析记录在执行过程中已实时写入 MongoDB，前端从数据库查明细
        ③ PROGRESS 阶段的 update_state 同理，不传 results 列表
    """
    # ── 在任务函数体内修复 sys.path（prefork 子进程路径继承不稳定）──
    import os as _os, sys as _sys
    _backend_dir = _os.path.dirname(_os.path.abspath(__file__))
    if _backend_dir not in _sys.path:
        _sys.path.insert(0, _backend_dir)

    from tasks import _run_single_encrypt_analyze, _build_summary, ALL_ALGORITHMS
    from core_logic.utils import load_image_safe
    from concurrent.futures import ThreadPoolExecutor, as_completed

    algorithms = selected_algorithms if selected_algorithms else ALL_ALGORITHMS

    # ── 构建任务列表 ─────────────────────────────────────────
    task_list = []
    for rec in image_records:
        img = load_image_safe(rec['path'])
        if img is None:
            logger.warning(f"无法加载图像: {rec['path']}")
            continue
        for algo in algorithms:
            task_list.append((
                img,
                rec['image_id'],
                rec['filename'],
                algo['name'],
                algo['params'],
            ))

    total       = len(task_list)
    completed   = 0
    success_cnt = 0
    failed_cnt  = 0
    all_results = []   # 仅用于内存内生成 summary，不放进返回值

    self.update_state(state='PROGRESS', meta={
        'current': 0, 'total': total, 'percent': 0,
        'success': 0, 'failed': 0,
        'status':  '初始化中...',
        # ★ 不在 meta 里放 results 列表，避免进度更新时也超限
    })

    if total == 0:
        return {
            'total': 0, 'success': 0, 'failed': 0,
            'summary': [], 'status': '没有可处理的图像',
        }

    # ── 并发执行 ─────────────────────────────────────────────
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_single_encrypt_analyze,
                img, iid, fname, aname, aparams,
                incremental    # ★ 透传增量参数
            ): None
            for img, iid, fname, aname, aparams in task_list
        }

        for future in as_completed(futures):
            result = future.result()
            completed += 1

            if result.get('skipped'):
                pass   # 跳过的不计入 success/failed
            elif result['success']:
                success_cnt += 1
            else:
                failed_cnt += 1

            # 只收集轻量字段用于生成 summary
            all_results.append(_slim(result))

            self.update_state(state='PROGRESS', meta={
                'current': completed,
                'total':   total,
                'percent': int(completed / total * 100),
                'success': success_cnt,
                'failed':  failed_cnt,
                'status':  f'正在处理 {completed}/{total}...',
            })

    summary = _build_summary(all_results)

    skipped_cnt = len(all_results) - success_cnt - failed_cnt

    return {
        'total':   total,
        'success': success_cnt,
        'failed':  failed_cnt,
        'skipped': skipped_cnt,   # ★ 新增：告知前端实际跳过了多少
        'summary': summary,
        'status':  '处理完成',
    }


def _slim(result: dict) -> dict:
    """
    从单条任务结果中提取轻量字段，去掉 base64 图像和直方图数组。
    这份精简结果只用于内存内生成 summary，不写入 Redis。
    """
    return {
        'success':           result.get('success', False),
        'algorithm':         result.get('algorithm', ''),
        'original_filename': result.get('original_filename', ''),
        'security_score':    result.get('security_score', 0),
        'encrypt_time_ms':   result.get('encrypt_time_ms', 0),
        'error':             result.get('error', ''),
        'metrics': {
            # 只保留数值型指标，不保留 histogram_original / histogram_encrypted
            k: v for k, v in (result.get('metrics') or {}).items()
            if isinstance(v, (int, float)) and v is not None
        },
    }