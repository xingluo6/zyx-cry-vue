# backend/app.py
import io
import os
import uuid
import atexit
import hashlib
import logging
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from config import TEMP_IMAGES_FOLDER, ALLOWED_EXTENSIONS, SECRET_KEY

from database import (
    IMAGE_TYPE_ORIGINAL, IMAGE_TYPE_ENCRYPTED,
    save_image_record, get_image_record, image_exists,
    find_image_by_hash,
    save_analysis_record, get_recent_analysis,
    get_algorithm_stats, get_score_trend, get_total_counts,
    get_all_analysis_for_training,
    get_image_library, get_image_library_all_ids,
    delete_image_and_derivatives, clean_intermediate_files,
    delete_analysis_records, get_analysis_date_range,
    get_experiment_stats,
)

# 同步批量处理（保留，供 Celery 不可用时降级使用）
from tasks import run_batch, ALL_ALGORITHMS

from core_logic.recommender import train_model, predict as recommend_predict, model_exists

import numpy as np
from core_logic.arnold_encryption import ArnoldEncryption
from core_logic.xor_encryption import XOREncryption
from core_logic.xxtea_encryption import XXTEAEncryption
from core_logic.aes_encryption import AESEncryption, AES_AVAILABLE
from core_logic.logistic_chaotic_encryption import LogisticChaoticEncryption
from core_logic.aesgcm_encryption import AESGCMEncryption
from core_logic.chacha20_encryption import ChaCha20Encryption
from core_logic.rsa_hybrid_encryption import RSAHybridEncryption
from core_logic.statistical_analysis import StatisticalAnalysis
from core_logic.utils import load_image_safe, save_image_safe, image_to_base64, CombinedEncryption

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY']    = SECRET_KEY
app.config['UPLOAD_FOLDER'] = TEMP_IMAGES_FOLDER
CORS(app)

# ── Celery 可用性检测（启动时检测一次，不强依赖）──
CELERY_AVAILABLE = False
try:
    from celery_app import celery_app, batch_process_task
    # 尝试 ping Redis
    celery_app.control.ping(timeout=1)
    CELERY_AVAILABLE = True
    logger.info("✅ Celery + Redis 已连接，批量处理使用异步模式")
except Exception:
    logger.warning("⚠️  Celery/Redis 不可用，批量处理将使用同步模式（功能不受影响）")


# ──────────────────────────────────────────────
# 启动/退出清理
# ──────────────────────────────────────────────

def _cleanup():
    try:
        result = clean_intermediate_files()
        for path in result.get('paths', []):
            if path and os.path.exists(path):
                try: os.remove(path)
                except Exception: pass
        if result['deleted_images'] > 0:
            logger.info(f"[清理] {result['deleted_images']} 条中间产物，analysis 已保留")
    except Exception as e:
        logger.warning(f"[清理] 失败: {e}")

atexit.register(_cleanup)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def allowed_file(f): return '.' in f and f.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def cvt(o):
    if isinstance(o, np.integer):  return int(o)
    if isinstance(o, np.floating): return float(o)
    if isinstance(o, np.ndarray):  return o.flatten().tolist()
    if isinstance(o, dict):  return {k: cvt(v) for k,v in o.items()}
    if isinstance(o, list):  return [cvt(e) for e in o]
    return o

def calc_sha256(b): return hashlib.sha256(b).hexdigest()

def save_uploaded_file(file) -> dict:
    fname      = file.filename
    file_bytes = file.read()
    file_size  = len(file_bytes)
    if file_size == 0: raise ValueError(f"文件为空: {fname}")
    file_hash = calc_sha256(file_bytes)
    existing  = find_image_by_hash(file_hash, file_size)
    if existing:
        rec = get_image_record(existing['_id'])
        return {"image_id": existing['_id'], "filename": fname,
                "original_shape": rec.get('shape',[]) if rec else [], "is_duplicate": True}
    ext       = fname.rsplit('.',1)[1].lower()
    image_id  = str(uuid.uuid4())
    file_path = os.path.join(TEMP_IMAGES_FOLDER, f"{image_id}.{ext}")
    with open(file_path, 'wb') as f: f.write(file_bytes)
    img = load_image_safe(file_path)
    if img is None:
        os.remove(file_path); raise ValueError(f"无法解码图像: {fname}")
    save_image_record(image_id, {
        "image_type": IMAGE_TYPE_ORIGINAL, "path": file_path,
        "shape": list(img.shape), "original_filename": fname,
        "file_hash": file_hash, "file_size": file_size,
    })
    return {"image_id": image_id, "filename": fname,
            "original_shape": list(img.shape), "is_duplicate": False}


def _do_encrypt(algorithm_name, params, orig_img):
    state = None
    if algorithm_name == "Arnold变换":
        e = ArnoldEncryption(); enc = e.encrypt(orig_img, params.get('iterations',10)); state = e.get_state()
    elif algorithm_name == "XOR加密":
        enc = XOREncryption(key_string=params.get('key','default_key'),
                            xor_mode=params.get('xor_mode','string'),
                            xor_byte=params.get('xor_byte',0x17)).encrypt(orig_img)
    elif algorithm_name == "XXTEA加密":
        enc = XXTEAEncryption(params.get('key','default_key')).encrypt_image(orig_img)
    elif algorithm_name == "AES加密":
        if not AES_AVAILABLE: raise RuntimeError("AES不可用，请安装PyCryptodome")
        enc = AESEncryption(key=params.get('key','aes_key'),mode=params.get('mode','CFB')).encrypt(orig_img)
    elif algorithm_name == "Logistic混沌加密":
        e = LogisticChaoticEncryption(key_string=params.get('key_string','logistic_key'),
            r=params.get('r',3.99),x0=params.get('x0',0.01),
            discard_iterations=params.get('discard_iterations',100))
        enc = e.encrypt(orig_img,use_key_params=params.get('use_key_params',True)); state = e.get_state()
    elif algorithm_name == "AES-GCM加密":
        enc = AESGCMEncryption(key_string=params.get('key_string','aesgcm_key')).encrypt(orig_img)
    elif algorithm_name == "ChaCha20加密":
        enc = ChaCha20Encryption(key_string=params.get('key_string','chacha20_key')).encrypt(orig_img)
    elif algorithm_name == "RSA混合加密":
        enc = RSAHybridEncryption(key_string=params.get('key_string','rsa_key')).encrypt(orig_img)
    else:
        raise ValueError(f"Invalid algorithm: {algorithm_name}")
    return enc, state


def _do_decrypt(algorithm_name, params, state, enc_img):
    if algorithm_name == "Arnold变换":
        e = ArnoldEncryption()
        if state: e.set_state(state)
        return e.decrypt(enc_img, params.get('iterations',10))
    elif algorithm_name == "XOR加密":
        return XOREncryption(key_string=params.get('key','default_key'),
                             xor_mode=params.get('xor_mode','string'),
                             xor_byte=params.get('xor_byte',0x17)).decrypt(enc_img)
    elif algorithm_name == "XXTEA加密":
        return XXTEAEncryption(params.get('key','default_key')).decrypt_image(enc_img)
    elif algorithm_name == "AES加密":
        if not AES_AVAILABLE: raise RuntimeError("AES不可用")
        return AESEncryption(key=params.get('key','aes_key'),mode=params.get('mode','CFB')).decrypt(enc_img)
    elif algorithm_name == "Logistic混沌加密":
        e = LogisticChaoticEncryption(key_string=params.get('key_string','logistic_key'),
            r=params.get('r',3.99),x0=params.get('x0',0.01),
            discard_iterations=params.get('discard_iterations',100))
        if state: e.set_state(state)
        return e.decrypt(enc_img,use_key_params=params.get('use_key_params',True))
    elif algorithm_name == "AES-GCM加密":
        return AESGCMEncryption(key_string=params.get('key_string','aesgcm_key')).decrypt(enc_img)
    elif algorithm_name == "ChaCha20加密":
        return ChaCha20Encryption(key_string=params.get('key_string','chacha20_key')).decrypt(enc_img)
    elif algorithm_name == "RSA混合加密":
        return RSAHybridEncryption(key_string=params.get('key_string','rsa_key')).decrypt(enc_img)
    else:
        raise ValueError(f"Invalid algorithm: {algorithm_name}")


def analysis_record(results, algo, orig_id, enc_id, fname, shape):
    return {
        'algorithm': algo, 'original_image_id': orig_id, 'encrypted_image_id': enc_id,
        'original_filename': fname, 'image_shape': list(shape) if shape else [],
        'security_score': results.get('security_score', 0),
        'metrics': {k: results.get(k) for k in [
            'entropy_original','entropy_encrypted',
            'correlation_h_original','correlation_h_encrypted',
            'correlation_v_original','correlation_v_encrypted',
            'correlation_d_original','correlation_d_encrypted',
            'chi2_original','chi2_encrypted',
            'mean_original','mean_encrypted',
            'variance_original','variance_encrypted',
            'std_dev_original','std_dev_encrypted',
            'arl_original','arl_encrypted','npcr','uaci','psnr',
        ]},
        'histogram_original':  results.get('histogram_original'),
        'histogram_encrypted': results.get('histogram_encrypted'),
    }


# ──────────────────────────────────────────────
# 下载 API
# ──────────────────────────────────────────────

@app.route('/api/download/<image_id>', methods=['GET'])
def download_image(image_id):
    rec = get_image_record(image_id)
    if not rec: return jsonify({"error": "Image not found"}), 404
    path = rec.get('path','')
    if not path or not os.path.exists(path):
        return jsonify({"error": "File not found on disk"}), 404
    base  = os.path.splitext(rec.get('original_filename','image'))[0]
    itype = rec.get('image_type','unknown')
    algo  = rec.get('algorithm','').replace('加密','').replace('变换','').replace(' ','_')
    if itype == IMAGE_TYPE_ENCRYPTED: name = f"{base}_encrypted_{algo}.png"
    elif itype == 'decrypted':         name = f"{base}_decrypted.png"
    else:                              name = f"{base}.png"
    return send_file(path, as_attachment=True, download_name=name, mimetype='image/png')


# ──────────────────────────────────────────────
# 图像库 API
# ──────────────────────────────────────────────

@app.route('/api/image_library', methods=['GET'])
def api_image_library():
    try: return jsonify(get_image_library(request.args.get('page',1,type=int),
                                          request.args.get('page_size',24,type=int))), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/image_library/all_ids', methods=['GET'])
def api_image_library_all_ids():
    try: return jsonify(get_image_library_all_ids()), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/image_library/delete', methods=['POST'])
def api_image_library_delete():
    ids = (request.get_json() or {}).get('image_ids', [])
    if not ids: return jsonify({"error": "image_ids 不能为空"}), 400
    total, errors = 0, []
    for iid in ids:
        try:
            r = delete_image_and_derivatives(iid)
            for p in r.get('paths',[]):
                if p and os.path.exists(p):
                    try: os.remove(p)
                    except Exception: pass
            total += r['count']
        except Exception as e: errors.append(f"{iid}: {e}")
    return jsonify({"deleted_count": total, "errors": errors}), 200

@app.route('/api/image_library/clean', methods=['POST'])
def api_image_library_clean():
    try:
        r = clean_intermediate_files(); fd = 0
        for p in r.get('paths',[]):
            if p and os.path.exists(p):
                try: os.remove(p); fd += 1
                except Exception: pass
        r['file_deleted'] = fd; return jsonify(r), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/image_library/thumbnail/<image_id>', methods=['GET'])
def api_image_thumbnail(image_id):
    import cv2
    rec = get_image_record(image_id)
    if not rec: return jsonify({"error": "Not found"}), 404
    try:
        img = load_image_safe(rec['path'])
        if img is None: return jsonify({"error": "Cannot load"}), 500
        h,w = img.shape[:2]; scale = min(200/max(h,w,1),1.0)
        if scale < 1.0:
            img = cv2.resize(img,(max(1,int(w*scale)),max(1,int(h*scale))),interpolation=cv2.INTER_AREA)
        return jsonify({"base64": image_to_base64(img)}), 200
    except Exception as e: return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# 分析记录管理
# ──────────────────────────────────────────────

@app.route('/api/analysis/delete',     methods=['POST'])
def api_analysis_delete():
    d = request.get_json() or {}
    try: return jsonify(delete_analysis_records(d.get('start_date'),d.get('end_date'),d.get('algorithm'))), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/analysis/date_range', methods=['GET'])
def api_analysis_date_range():
    try: return jsonify(get_analysis_date_range()), 200
    except Exception as e: return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# 核心加密 API
# ──────────────────────────────────────────────

@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files: return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if not file.filename: return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename): return jsonify({"error": "File type not allowed"}), 400
    try: return jsonify(save_uploaded_file(file)), 200
    except Exception as e: return jsonify({"error": str(e)}), 500


@app.route('/api/encrypt', methods=['POST'])
def encrypt_image_api():
    data = request.get_json()
    iid  = data.get('image_id'); algo = data.get('algorithm'); params = data.get('params',{})
    if not iid or not algo: return jsonify({"error": "Missing params"}), 400
    if not image_exists(iid): return jsonify({"error": "Original image not found"}), 404
    try:
        orig_info = get_image_record(iid); oi = load_image_safe(orig_info['path'])
        if oi is None: return jsonify({"error": "Failed to load"}), 500
        enc, state = _do_encrypt(algo, params, oi)
        if enc is None: return jsonify({"error": "Encryption failed"}), 500
        enc_id = str(uuid.uuid4()); enc_path = os.path.join(app.config['UPLOAD_FOLDER'],f"{enc_id}.png")
        if not save_image_safe(enc, enc_path): return jsonify({"error": "Save failed"}), 500
        save_image_record(enc_id,{"image_type":IMAGE_TYPE_ENCRYPTED,"path":enc_path,
            "shape":list(enc.shape),"original_image_id":iid,"algorithm":algo,
            "params":params,"state":state,"original_filename":orig_info.get('original_filename','')})
        return jsonify({"encrypted_image_id":enc_id,"encrypted_image_base64":image_to_base64(enc),
                        "encrypted_shape":list(enc.shape),"algorithm_state":state}), 200
    except Exception as e: logger.error(f"encrypt: {e}",exc_info=True); return jsonify({"error":str(e)}),500


@app.route('/api/decrypt', methods=['POST'])
def decrypt_image_api():
    data=request.get_json(); enc_id=data.get('encrypted_image_id')
    algo=data.get('algorithm'); state=data.get('algorithm_state')
    if not enc_id or not algo: return jsonify({"error":"Missing params"}),400
    if not image_exists(enc_id): return jsonify({"error":"Encrypted image not found"}),404
    try:
        enc_rec=get_image_record(enc_id); enc_img=load_image_safe(enc_rec['path'])
        if enc_img is None: return jsonify({"error":"Failed to load"}),500
        # ★ 修复：优先使用数据库中存储的加密参数
        # AES-GCM/ChaCha20/RSA 混合加密用 key_string 派生密钥，
        # 解密必须和加密使用完全相同的 key_string。
        # 合并策略：stored_params 优先级高于前端传来的 params
        stored_params   = enc_rec.get("params") or {}
        frontend_params = data.get("params") or {}
        params = {**frontend_params, **stored_params}
        dec_img=_do_decrypt(algo,params,state,enc_img)
        if dec_img is None: return jsonify({"error":"Decryption failed"}),500
        dec_id=str(uuid.uuid4()); dec_path=os.path.join(app.config['UPLOAD_FOLDER'],f"{dec_id}.png")
        save_image_safe(dec_img,dec_path)
        save_image_record(dec_id,{"image_type":"decrypted","path":dec_path,"shape":list(dec_img.shape),
            "original_image_id":enc_rec.get('original_image_id',''),
            "original_filename":enc_rec.get('original_filename','')})
        return jsonify({"decrypted_image_id":dec_id,"decrypted_image_base64":image_to_base64(dec_img),
                        "decrypted_shape":list(dec_img.shape)}), 200
    except Exception as e: logger.error(f"decrypt: {e}",exc_info=True); return jsonify({"error":str(e)}),500


@app.route('/api/analyze', methods=['POST'])
def analyze_images_api():
    data=request.get_json(); oid=data.get('original_image_id'); eid=data.get('encrypted_image_id')
    if not oid or not eid: return jsonify({"error":"Missing ids"}),400
    if not image_exists(oid) or not image_exists(eid): return jsonify({"error":"Not found"}),404
    try:
        oi=load_image_safe(get_image_record(oid)['path']); ei=load_image_safe(get_image_record(eid)['path'])
        if oi is None or ei is None: return jsonify({"error":"Failed to load"}),500
        r=cvt(StatisticalAnalysis().analyze_security(oi,ei))
        algo=get_image_record(eid).get('algorithm','未知算法'); orig=get_image_record(oid)
        save_analysis_record(analysis_record(r,algo,oid,eid,orig.get('original_filename',''),orig.get('shape',[])))
        return jsonify({"analysis_results":r,"formatted_report":fmt_report(r,algo)}), 200
    except Exception as e: logger.error(f"analyze: {e}",exc_info=True); return jsonify({"error":str(e)}),500


@app.route('/api/combined_encrypt', methods=['POST'])
def combined_encrypt_api():
    data=request.get_json(); iid=data.get('image_id'); chain=data.get('algorithms',[])
    if not iid or not chain: return jsonify({"error":"Missing params"}),400
    if not image_exists(iid): return jsonify({"error":"Not found"}),404
    try:
        orig_info=get_image_record(iid); oi=load_image_safe(orig_info['path'])
        if oi is None: return jsonify({"error":"Failed to load"}),500
        ce=CombinedEncryption()
        for s in chain: ce.add_algorithm(s['name'],s.get('params',{}))
        ei=ce.encrypt(oi)
        if ei is None: return jsonify({"error":"Failed"}),500
        eid=str(uuid.uuid4()); path=os.path.join(app.config['UPLOAD_FOLDER'],f"{eid}.png")
        if not save_image_safe(ei,path): return jsonify({"error":"Save failed"}),500
        st=ce.get_state()
        save_image_record(eid,{"image_type":IMAGE_TYPE_ENCRYPTED,"path":path,"shape":list(ei.shape),
            "original_image_id":iid,"algorithm":"Combined Encryption","combined_encryptor_state":st,
            "original_filename":orig_info.get('original_filename','')})
        return jsonify({"encrypted_image_id":eid,"encrypted_image_base64":image_to_base64(ei),
                        "encrypted_shape":list(ei.shape),"combined_encryptor_state":st}), 200
    except Exception as e: logger.error(f"combined_encrypt: {e}",exc_info=True); return jsonify({"error":str(e)}),500


@app.route('/api/combined_decrypt', methods=['POST'])
def combined_decrypt_api():
    data=request.get_json(); eid=data.get('encrypted_image_id'); state=data.get('combined_encryptor_state')
    if not eid or not state: return jsonify({"error":"Missing params"}),400
    if not image_exists(eid): return jsonify({"error":"Not found"}),404
    try:
        enc_rec=get_image_record(eid); ei=load_image_safe(enc_rec['path'])
        if ei is None: return jsonify({"error":"Failed to load"}),500
        di=CombinedEncryption.from_state(state).decrypt(ei)
        if di is None: return jsonify({"error":"Failed"}),500
        dec_id=str(uuid.uuid4()); dec_path=os.path.join(app.config['UPLOAD_FOLDER'],f"{dec_id}.png")
        save_image_safe(di,dec_path)
        save_image_record(dec_id,{"image_type":"decrypted","path":dec_path,"shape":list(di.shape),
            "original_image_id":enc_rec.get('original_image_id',''),
            "original_filename":enc_rec.get('original_filename','')})
        return jsonify({"decrypted_image_id":dec_id,"decrypted_image_base64":image_to_base64(di),
                        "decrypted_shape":list(di.shape)}), 200
    except Exception as e: logger.error(f"combined_decrypt: {e}",exc_info=True); return jsonify({"error":str(e)}),500


@app.route('/api/combined_analyze', methods=['POST'])
def combined_analyze_api():
    data=request.get_json(); oid=data.get('original_image_id'); eid=data.get('encrypted_image_id')
    if not oid or not eid: return jsonify({"error":"Missing ids"}),400
    if not image_exists(oid) or not image_exists(eid): return jsonify({"error":"Not found"}),404
    try:
        oi=load_image_safe(get_image_record(oid)['path']); ei=load_image_safe(get_image_record(eid)['path'])
        if oi is None or ei is None: return jsonify({"error":"Failed to load"}),500
        r=cvt(StatisticalAnalysis().analyze_security(oi,ei)); orig=get_image_record(oid)
        save_analysis_record(analysis_record(r,"Combined Encryption",oid,eid,
            orig.get('original_filename',''),orig.get('shape',[])))
        return jsonify({"analysis_results":r,"formatted_report":fmt_report(r,"Combined Encryption")}), 200
    except Exception as e: logger.error(f"combined_analyze: {e}",exc_info=True); return jsonify({"error":str(e)}),500


# ──────────────────────────────────────────────
# 批量处理 API（异步优先，同步降级）
# ──────────────────────────────────────────────

@app.route('/api/batch_upload', methods=['POST'])
def batch_upload():
    if 'files' not in request.files: return jsonify({"error":"No files"}),400
    uploaded, errors = [], []
    for file in request.files.getlist('files'):
        if not file.filename: continue
        if not allowed_file(file.filename): errors.append(f"{file.filename}: 类型不支持"); continue
        try: uploaded.append(save_uploaded_file(file))
        except Exception as e: errors.append(f"{file.filename}: {e}")
    new_c = sum(1 for u in uploaded if not u['is_duplicate'])
    dup_c = sum(1 for u in uploaded if u['is_duplicate'])
    return jsonify({"uploaded":uploaded,"errors":errors,"count":len(uploaded),
                    "new_count":new_c,"dup_count":dup_c}), 200


@app.route('/api/batch_process', methods=['POST'])
def batch_process():
    data        = request.get_json()
    image_ids   = data.get('image_ids', [])
    algorithms  = data.get('algorithms', None)
    max_workers = data.get('max_workers', 4)
    # ★ 新增：从请求体读取 incremental 参数，默认 True
    incremental = data.get('incremental', True)

    if not image_ids: return jsonify({"error": "image_ids 不能为空"}), 400

    recs, missing = [], []
    for iid in image_ids:
        rec = get_image_record(iid)
        if rec is None: missing.append(iid); continue
        recs.append({"image_id": iid, "path": rec['path'],
                     "filename": rec.get('original_filename', iid)})
    if missing: return jsonify({"error": f"不存在: {missing}"}), 404

    selected_algorithms = algorithms if algorithms else [
        {"name": a["name"], "params": a.get("params", {})} for a in ALL_ALGORITHMS
    ]

    # ── 异步模式（Celery 可用）──
    if CELERY_AVAILABLE:
        try:
            # ★ 把 incremental 传给 Celery 任务
            task = batch_process_task.delay(
                recs, selected_algorithms, max_workers, incremental
            )
            logger.info(f"[async] 批量任务已提交 task_id={task.id} incremental={incremental}")
            return jsonify({
                "mode":    "async",
                "task_id": task.id,
                "total":   len(recs) * len(selected_algorithms),
                "message": f"任务已提交，共 {len(recs)} 张图片 × {len(selected_algorithms)} 种算法",
            }), 202
        except Exception as e:
            logger.warning(f"[async] Celery 提交失败，降级到同步: {e}")

    # ── 同步降级模式 ──
    logger.info(f"[sync] 同步批量处理 {len(recs)} 张图片 incremental={incremental}")
    try:
        # ★ 把 incremental 传给 run_batch
        result = run_batch(recs, algorithms, max_workers, incremental)
        result['mode'] = 'sync'
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"batch sync: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/task_status/<task_id>', methods=['GET'])
def task_status(task_id):
    """
    查询异步任务进度。

    返回格式：
    {
        "task_id":  "...",
        "state":    "PENDING" | "STARTED" | "PROGRESS" | "SUCCESS" | "FAILURE",
        "percent":  0-100,
        "current":  已完成数,
        "total":    总任务数,
        "success":  成功数,
        "failed":   失败数,
        "status":   状态描述文字,
        "result":   完整结果（仅 SUCCESS 时存在）,
        "error":    错误信息（仅 FAILURE 时存在）,
    }
    """
    if not CELERY_AVAILABLE:
        return jsonify({"error": "Celery 不可用"}), 503

    try:
        from celery_app import celery_app as _celery
        from celery.result import AsyncResult

        task   = AsyncResult(task_id, app=_celery)
        state  = task.state

        if state == 'PENDING':
            return jsonify({
                "task_id": task_id, "state": "PENDING",
                "percent": 0, "current": 0, "total": 0,
                "status": "等待处理...",
            })

        elif state == 'STARTED':
            return jsonify({
                "task_id": task_id, "state": "STARTED",
                "percent": 0, "current": 0, "total": 0,
                "status": "任务已启动...",
            })

        elif state == 'PROGRESS':
            meta = task.info or {}
            return jsonify({
                "task_id": task_id,
                "state":   "PROGRESS",
                "percent": meta.get('percent', 0),
                "current": meta.get('current', 0),
                "total":   meta.get('total', 0),
                "success": meta.get('success', 0),
                "failed":  meta.get('failed', 0),
                "status":  meta.get('status', '处理中...'),
                # 注意：results 可能很大，此处不返回，SUCCESS 时再返回完整结果
            })

        elif state == 'SUCCESS':
            result = task.result or {}
            return jsonify({
                "task_id": task_id,
                "state":   "SUCCESS",
                "percent": 100,
                "current": result.get('total', 0),
                "total":   result.get('total', 0),
                "success": result.get('success', 0),
                "failed":  result.get('failed', 0),
                "status":  "处理完成",
                "result":  result,
            })

        elif state == 'FAILURE':
            return jsonify({
                "task_id": task_id,
                "state":   "FAILURE",
                "percent": 0,
                "status":  "处理失败",
                "error":   str(task.info),
            })

        else:
            return jsonify({"task_id": task_id, "state": state, "percent": 0})

    except Exception as e:
        logger.error(f"task_status {task_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/task_cancel/<task_id>', methods=['POST'])
def task_cancel(task_id):
    """取消异步任务"""
    if not CELERY_AVAILABLE:
        return jsonify({"error": "Celery 不可用"}), 503
    try:
        from celery_app import celery_app as _celery
        _celery.control.revoke(task_id, terminate=True)
        return jsonify({"cancelled": True, "task_id": task_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/celery_status', methods=['GET'])
def celery_status():
    """返回 Celery 可用状态，供前端判断显示模式"""
    return jsonify({"available": CELERY_AVAILABLE}), 200


@app.route('/api/batch_algorithms', methods=['GET'])
def get_batch_algorithms():
    return jsonify([{"name": a["name"], "label": a["name"]} for a in ALL_ALGORITHMS]), 200


# ──────────────────────────────────────────────
# Dashboard API
# ──────────────────────────────────────────────

@app.route('/api/dashboard/stats',           methods=['GET'])
def dashboard_stats():
    try: return jsonify(get_total_counts()), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/algorithm_stats', methods=['GET'])
def dashboard_algorithm_stats():
    try: return jsonify(get_algorithm_stats()), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/score_trend',     methods=['GET'])
def dashboard_score_trend():
    try: return jsonify(get_score_trend(request.args.get('limit',50,type=int))), 200
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/recent',          methods=['GET'])
def dashboard_recent():
    try: return jsonify(get_recent_analysis(request.args.get('limit',20,type=int))), 200
    except Exception as e: return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
# 推荐模型 API
# ──────────────────────────────────────────────

@app.route('/api/recommend/train',   methods=['POST'])
def recommend_train():
    try:
        records=get_all_analysis_for_training()
        if not records: return jsonify({"success":False,"message":"没有分析记录"}),200
        return jsonify(train_model(records)), 200
    except Exception as e: return jsonify({"success":False,"message":str(e)}),500

@app.route('/api/recommend/predict', methods=['POST'])
def recommend_predict_api():
    data=request.get_json(); iid=data.get('image_id')
    if not iid: return jsonify({"error":"Missing image_id"}),400
    if not image_exists(iid): return jsonify({"error":"Not found"}),404
    try:
        img=load_image_safe(get_image_record(iid)['path'])
        if img is None: return jsonify({"error":"Failed to load"}),500
        return jsonify(recommend_predict(img)), 200
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route('/api/recommend/status',  methods=['GET'])
def recommend_status():
    return jsonify({"model_exists":model_exists()}), 200


# ──────────────────────────────────────────────
# 实验对比 API
# ──────────────────────────────────────────────

@app.route('/api/experiment/stats', methods=['POST'])
def experiment_stats():
    data=request.get_json() or {}
    try: return jsonify(get_experiment_stats(data.get('image_ids'),data.get('algorithm_names'))), 200
    except Exception as e: logger.error(f"experiment_stats: {e}",exc_info=True); return jsonify({"error":str(e)}),500

@app.route('/api/experiment/algorithms', methods=['GET'])
def experiment_algorithms():
    try:
        from database import get_db
        return jsonify(sorted(get_db()['analysis'].distinct('algorithm'))), 200
    except Exception as e: return jsonify({"error":str(e)}),500


# ──────────────────────────────────────────────
# 数据导出 API
# ──────────────────────────────────────────────

@app.route('/api/export/dashboard_excel', methods=['GET'])
def export_dashboard_excel_api():
    try:
        from export_utils import export_dashboard_excel
        excel_bytes = export_dashboard_excel(get_algorithm_stats(), get_recent_analysis(200), get_score_trend(100))
        fname = f"加密分析汇总_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(io.BytesIO(excel_bytes), as_attachment=True, download_name=fname,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e: logger.error(f"export excel: {e}",exc_info=True); return jsonify({"error":str(e)}),500

@app.route('/api/export/batch_excel', methods=['POST'])
def export_batch_excel_api():
    try:
        from export_utils import export_batch_excel
        batch_result = (request.get_json() or {}).get('batch_result')
        if not batch_result: return jsonify({"error":"Missing batch_result"}),400
        excel_bytes = export_batch_excel(batch_result)
        fname = f"批量处理结果_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return send_file(io.BytesIO(excel_bytes), as_attachment=True, download_name=fname,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e: logger.error(f"export batch excel: {e}",exc_info=True); return jsonify({"error":str(e)}),500

@app.route('/api/export/experiment_pdf', methods=['POST'])
def export_experiment_pdf_api():
    try:
        from export_utils import export_experiment_pdf
        data     = request.get_json() or {}
        exp_data = get_experiment_stats(data.get('image_ids'), data.get('algorithm_names'))
        if not exp_data: return jsonify({"error":"没有足够的实验数据"}),400
        pdf_bytes = export_experiment_pdf(exp_data)
        fname = f"实验对比报告_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), as_attachment=True, download_name=fname, mimetype='application/pdf')
    except Exception as e: logger.error(f"export pdf: {e}",exc_info=True); return jsonify({"error":str(e)}),500


# ──────────────────────────────────────────────
# 报告格式化
# ──────────────────────────────────────────────

def fmt_report(s, algo):
    lines = [
        "数字图像加密安全性分析报告","="*50,
        f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"加密算法: {algo}",f"综合安全评分: {s['security_score']}/100","="*50,
        f"1. 信息熵: {s['entropy_original']:.4f} → {s['entropy_encrypted']:.4f}",
        f"2. 相关性: {s['correlation_h_original']:.6f}/{s['correlation_v_original']:.6f}/{s['correlation_d_original']:.6f}",
        f"   → {s['correlation_h_encrypted']:.6f}/{s['correlation_v_encrypted']:.6f}/{s['correlation_d_encrypted']:.6f}",
        f"3. 卡方: {s['chi2_original']:.2f} → {s['chi2_encrypted']:.2f}",
        f"4. 均值/方差: {s['mean_original']:.2f}/{s['variance_original']:.2f} → {s['mean_encrypted']:.2f}/{s['variance_encrypted']:.2f}",
        f"5. ARL: {s['arl_original']:.4f} → {s['arl_encrypted']:.4f}",
        f"6. NPCR: {s['npcr']:.4f}%  UACI: {s['uaci']:.4f}%",
        f"7. PSNR: {s['psnr']:.2f} dB","="*50,"结论:",
    ]
    e=s['entropy_encrypted']
    if e>7.9: lines.append("• ✓ 信息熵极高，加密效果优秀")
    elif e>7.5: lines.append("• ✓ 信息熵良好，加密效果较好")
    elif e>7.0: lines.append("• △ 信息熵一般，加密效果尚可")
    else: lines.append("• ✗ 信息熵较低，加密效果不理想")
    sc=s['security_score']
    if sc>=80: lines.append("• 🎯 综合评分：优秀")
    elif sc>=65: lines.append("• 🎯 综合评分：良好")
    elif sc>=50: lines.append("• 🎯 综合评分：中等")
    else: lines.append("• 🎯 综合评分：较差")
    lines+=["="*50,"报告结束","="*50]
    return "\n".join(lines)


# ──────────────────────────────────────────────
# 静态文件服务（放最后）
# ──────────────────────────────────────────────

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_vue_app(path):
    if path.startswith('api/'): return jsonify({"error":"Not found"}),404
    fp = os.path.join(app.root_path,'static',path)
    if path and os.path.exists(fp):
        return send_from_directory(os.path.join(app.root_path,'static'),path)
    return send_from_directory(os.path.join(app.root_path,'templates'),'index.html')


if __name__ == '__main__':
    _cleanup()
    app.run(port=5000, debug=False)