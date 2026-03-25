#!/usr/bin/env python3
"""
离线批量数据集处理脚本（增强版）。

支持三种模式：
  --mode dir      扫描本地目录上传并处理（默认）
  --mode library  直接处理图像库中已有的图片（无需上传）
  --mode smart    智能增量模式：图像库已有图片优先，再补充新图片

使用示例：
  # 处理图像库中所有已有图片，对所有算法补全分析
  python batch_dataset.py --mode library

  # 智能模式：库中图片补全 + 新图片补充到指定数量
  python batch_dataset.py --mode smart --dir ./images --max 50

  # 目录模式（原有功能）
  python batch_dataset.py --mode dir --dir ./images --max 100

  # 只跑特定算法
  python batch_dataset.py --mode library --algorithms "AES-GCM加密,ChaCha20加密"
"""

import os
import sys
import time
import argparse
import random
from pathlib import Path
from collections import defaultdict

try:
    import requests
except ImportError:
    print("请先安装 requests: pip install requests")
    sys.exit(1)

SUPPORTED_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}

ALL_ALGORITHM_NAMES = [
    "Arnold变换",
    "XOR加密",
    "XXTEA加密",
    "AES加密",
    "Logistic混沌加密",
    "AES-GCM加密",
    "ChaCha20加密",
    "RSA混合加密",
]


# ──────────────────────────────────────────────
# API 封装
# ──────────────────────────────────────────────

def api_get(session, backend, path, **kwargs):
    try:
        resp = session.get(f"{backend}{path}", timeout=10, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ⚠ GET {path} 失败: {e}")
        return None


def api_post(session, backend, path, json=None, files=None, timeout=600):
    try:
        resp = session.post(f"{backend}{path}", json=json, files=files, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ⚠ POST {path} 失败: {e}")
        return None


def check_backend(session, backend) -> bool:
    result = api_get(session, backend, '/api/dashboard/stats')
    if result is None:
        print(f"❌ 无法连接到后端 {backend}")
        print("   请先启动后端: python app.py")
        return False
    print(f"✅ 后端连接成功")
    print(f"   图像总数: {result.get('image_count', 0)}")
    print(f"   分析记录: {result.get('analysis_count', 0)}")
    print(f"   算法种类: {result.get('algo_count', 0)}")
    return True


def get_library_images(session, backend) -> list:
    """获取图像库中所有已上传的图像"""
    images = []
    page   = 1
    while True:
        result = api_get(session, backend, '/api/image_library',
                         params={'page': page, 'page_size': 100})
        if not result or not result.get('items'):
            break
        images.extend(result['items'])
        if page >= result.get('pages', 1):
            break
        page += 1
    return images


def get_analyzed_combinations(session, backend) -> set:
    """
    获取已分析过的（image_id, algorithm）组合，
    用于增量模式跳过已处理的任务。
    """
    result = api_get(session, backend, '/api/dashboard/recent', params={'limit': 5000})
    if not result:
        return set()
    combos = set()
    for rec in result:
        oid  = rec.get('original_image_id', '')
        algo = rec.get('algorithm', '')
        if oid and algo:
            combos.add((oid, algo))
    return combos


def upload_image(session, backend, image_path) -> tuple:
    fname = os.path.basename(image_path)
    try:
        with open(image_path, 'rb') as f:
            result = api_post(session, backend, '/api/upload_image',
                              files={'file': (fname, f)}, timeout=30)
        if result:
            flag = "（已存在）" if result.get('is_duplicate') else "（新增）"
            return result['image_id'], flag
    except Exception as e:
        print(f"  ⚠ 上传失败 {fname}: {e}")
    return None, ''


def run_batch_for_images(session, backend, image_ids, algorithm_names, max_workers) -> dict:
    result = api_post(session, backend, '/api/batch_process', json={
        "image_ids":   image_ids,
        "algorithms":  [{"name": n, "params": {}} for n in algorithm_names],
        "max_workers": max_workers,
    }, timeout=600)
    return result or {}


# ──────────────────────────────────────────────
# 三种处理模式
# ──────────────────────────────────────────────

def mode_library(session, backend, selected_algos, max_workers, incremental=True):
    """
    库模式：直接处理图像库中已有的图片。
    incremental=True 时跳过已分析过的组合。
    """
    print("\n📚 图像库模式：读取已有图像进行分析")

    images = get_library_images(session, backend)
    if not images:
        print("  图像库为空，请先上传图片（可用 --mode dir）")
        return 0, 0

    print(f"  图像库共 {len(images)} 张图片")

    if incremental:
        print("  🔍 检查已分析记录（增量模式）...")
        analyzed = get_analyzed_combinations(session, backend)
        print(f"  已有 {len(analyzed)} 个（图像×算法）组合的分析记录")
    else:
        analyzed = set()

    # 找出需要补全的任务
    todo_by_image = defaultdict(list)
    for img in images:
        iid = img['image_id']
        for algo in selected_algos:
            if (iid, algo) not in analyzed:
                todo_by_image[iid].append(algo)

    total_todo = sum(len(v) for v in todo_by_image.items())
    if total_todo == 0 and incremental:
        print("  ✅ 所有图像×算法组合均已分析，无需重复处理")
        return 0, 0

    need_process = {iid: algos for iid, algos in todo_by_image.items() if algos}
    print(f"  需要补全：{len(need_process)} 张图片，"
          f"共 {sum(len(v) for v in need_process.values())} 个任务")

    return _run_batches(session, backend, need_process, max_workers)


def mode_dir(session, backend, directory, max_count, selected_algos, max_workers, batch_size):
    """目录模式：扫描本地目录，上传并处理"""
    print(f"\n📁 目录模式：扫描 {directory}")

    paths = _scan_images(directory, max_count)
    if not paths:
        print("  没有找到可用图片")
        return 0, 0

    print(f"  找到 {len(paths)} 张图片")

    total_success = 0
    total_failed  = 0

    for i in range(0, len(paths), batch_size):
        batch     = paths[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_b   = (len(paths) + batch_size - 1) // batch_size
        print(f"\n  📦 批次 {batch_num}/{total_b}（{len(batch)} 张）")

        image_ids = []
        for path in batch:
            iid, flag = upload_image(session, backend, path)
            if iid:
                image_ids.append(iid)
                print(f"    ✓ {os.path.basename(path)} {flag}")

        if not image_ids:
            continue

        print(f"    ⏳ 运行 {len(selected_algos)} 种算法...")
        t0     = time.time()
        result = run_batch_for_images(session, backend, image_ids, selected_algos, max_workers)
        elapsed = time.time() - t0

        s = result.get('success', 0); f = result.get('failed', 0)
        total_success += s; total_failed += f
        print(f"    ✅ {s} 成功，{f} 失败，{elapsed:.1f}s")
        _print_summary(result.get('summary', []))

    return total_success, total_failed


def mode_smart(session, backend, directory, max_count, selected_algos, max_workers, batch_size):
    """
    智能增量模式：
    1. 先对库中已有图片补全缺失的算法分析
    2. 再从目录补充新图片直到达到 max_count
    """
    print("\n🧠 智能增量模式")

    # Step 1: 处理已有图片
    s1, f1 = mode_library(session, backend, selected_algos, max_workers, incremental=True)

    # Step 2: 检查还需要多少新图片
    current_count = len(get_library_images(session, backend))
    need_new      = max(0, max_count - current_count)

    if need_new == 0:
        print(f"\n  图像库已有 {current_count} 张，无需补充新图片")
        return s1, f1

    print(f"\n  图像库已有 {current_count} 张，还需补充 {need_new} 张新图片")

    if not directory:
        print("  ⚠ 未指定 --dir，跳过新图片补充")
        return s1, f1

    s2, f2 = mode_dir(session, backend, directory, need_new, selected_algos, max_workers, batch_size)
    return s1 + s2, f1 + f2


# ──────────────────────────────────────────────
# 内部辅助函数
# ──────────────────────────────────────────────

def _scan_images(directory, max_count) -> list:
    root  = Path(directory)
    if not root.exists():
        print(f"  ❌ 目录不存在: {directory}"); return []
    paths = []
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            paths.append(str(p))
        if len(paths) >= max_count * 3:
            break
    random.shuffle(paths)
    return paths[:max_count]


def _run_batches(session, backend, need_process: dict, max_workers: int, batch_size: int = 20):
    """按批次处理需要补全的任务"""
    all_iids   = list(need_process.keys())
    total_s    = 0
    total_f    = 0

    for i in range(0, len(all_iids), batch_size):
        chunk   = all_iids[i:i + batch_size]
        batch_n = i // batch_size + 1
        total_b = (len(all_iids) + batch_size - 1) // batch_size

        # 收集本批次需要运行的算法（取并集）
        algos_needed = set()
        for iid in chunk:
            algos_needed.update(need_process[iid])

        print(f"\n  📦 批次 {batch_n}/{total_b}（{len(chunk)} 张 × {len(algos_needed)} 算法）")
        t0     = time.time()
        result = run_batch_for_images(session, backend, chunk,
                                      list(algos_needed), max_workers)
        elapsed = time.time() - t0

        s = result.get('success', 0); f = result.get('failed', 0)
        total_s += s; total_f += f
        print(f"    ✅ {s} 成功，{f} 失败，{elapsed:.1f}s")
        _print_summary(result.get('summary', []))

    return total_s, total_f


def _print_summary(summary):
    if not summary: return
    print("    📊 评分汇总（前5）：")
    for item in summary[:5]:
        print(f"       {item['algorithm']:<20} "
              f"均分={item['avg_score']}  耗时={item['avg_time_ms']}ms")


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='图像加密平台 — 离线批量数据集处理脚本')
    parser.add_argument('--mode',       choices=['dir','library','smart'], default='dir',
                        help='处理模式：dir=目录模式, library=图像库模式, smart=智能增量')
    parser.add_argument('--dir',        type=str, default='',
                        help='图片目录路径（dir/smart 模式需要）')
    parser.add_argument('--max',        type=int, default=100,
                        help='最多处理图片数量（默认100）')
    parser.add_argument('--workers',    type=int, default=4,
                        help='并发线程数（默认4）')
    parser.add_argument('--algorithms', type=str, default='',
                        help='逗号分隔的算法名（默认全部8种）')
    parser.add_argument('--backend',    type=str, default='http://127.0.0.1:5000',
                        help='后端地址（默认 http://127.0.0.1:5000）')
    parser.add_argument('--batch-size', type=int, default=20,
                        help='每批处理图片数（默认20）')
    parser.add_argument('--no-incremental', action='store_true',
                        help='library/smart 模式下不跳过已分析的记录（强制全量重跑）')
    args = parser.parse_args()

    # 解析算法列表
    if args.algorithms.strip():
        selected = [a.strip() for a in args.algorithms.split(',') if a.strip()]
        invalid  = [a for a in selected if a not in ALL_ALGORITHM_NAMES]
        if invalid:
            print(f"❌ 未知算法: {invalid}")
            print(f"   可用：{ALL_ALGORITHM_NAMES}")
            sys.exit(1)
    else:
        selected = ALL_ALGORITHM_NAMES

    print("=" * 62)
    print("图像加密分析平台 — 离线批量数据集处理脚本（增强版）")
    print("=" * 62)
    print(f"模式:     {args.mode}")
    if args.dir: print(f"目录:     {args.dir}")
    print(f"算法数:   {len(selected)} 种 → {', '.join(selected)}")
    print(f"并发:     {args.workers} 线程")
    print(f"后端:     {args.backend}")
    print("=" * 62)

    session = requests.Session()
    if not check_backend(session, args.backend):
        sys.exit(1)

    t_start = time.time()

    if args.mode == 'library':
        s, f = mode_library(session, args.backend, selected, args.workers,
                             incremental=not args.no_incremental)
    elif args.mode == 'dir':
        if not args.dir:
            print("❌ dir 模式需要指定 --dir 参数")
            sys.exit(1)
        s, f = mode_dir(session, args.backend, args.dir, args.max,
                        selected, args.workers, args.batch_size)
    elif args.mode == 'smart':
        s, f = mode_smart(session, args.backend, args.dir, args.max,
                          selected, args.workers, args.batch_size)

    elapsed = time.time() - t_start
    print("\n" + "=" * 62)
    print("🎉 处理完成！")
    print(f"   成功: {s} 条 | 失败: {f} 条 | 耗时: {elapsed:.1f}s")

    # 最终状态
    stats = api_get(session, args.backend, '/api/dashboard/stats')
    if stats:
        print(f"\n📈 数据库当前状态：")
        print(f"   图像总数：{stats.get('image_count', 0)}")
        print(f"   分析记录：{stats.get('analysis_count', 0)}")
        print(f"   算法种类：{stats.get('algo_count', 0)}")

    print("=" * 62)
    print("💡 接下来：")
    print("   1. 打开「数据大屏」查看图表")
    print("   2. 点击「训练推荐模型」")
    print("   3. 打开「实验对比」查看论文格式表格")


if __name__ == '__main__':
    main()