# backend/core_logic/recommender.py
import os
import pickle
import logging
import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(_MODEL_DIR, 'recommend_model.pkl')

# ✅ 新增三种算法
ALGO_LABELS = [
    'Arnold变换',
    'XOR加密',
    'XXTEA加密',
    'AES加密',
    'Logistic混沌加密',
    'AES-GCM加密',
    'ChaCha20加密',
    'RSA混合加密',
]

MIN_SAMPLES = 10


def extract_image_features(image: np.ndarray) -> list:
    import cv2
    from scipy.stats import entropy as scipy_entropy

    if len(image.shape) == 3:
        gray          = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        channel_count = image.shape[2]
    else:
        gray          = image
        channel_count = 1

    h, w  = gray.shape
    flat  = gray.flatten().astype(np.float32)

    mean_pixel   = float(np.mean(flat)) / 255.0
    std_pixel    = float(np.std(flat))  / 128.0

    hist      = np.bincount(gray.flatten(), minlength=256).astype(float)
    hist_prob = hist / hist.sum()
    hist_prob = hist_prob[hist_prob > 0]
    orig_entropy = float(scipy_entropy(hist_prob, base=2)) / 8.0

    ratio        = w / max(h, 1)
    aspect_ratio = ratio / (ratio + 1)
    channel_norm = (channel_count - 1) / 3.0
    total_pixels = h * w
    size_cat     = 0.0 if total_pixels < 128*1024 else (0.5 if total_pixels < 512*1024 else 1.0)

    return [mean_pixel, std_pixel, orig_entropy, aspect_ratio, channel_norm, size_cat]


def _extract_features_from_record(record: dict):
    metrics = record.get('metrics', {})
    shape   = record.get('image_shape', [])

    mean_orig    = metrics.get('mean_original')
    std_orig     = metrics.get('std_dev_original')
    entropy_orig = metrics.get('entropy_original')

    if any(v is None for v in [mean_orig, std_orig, entropy_orig]):
        return None

    if len(shape) >= 2:
        h, w          = shape[0], shape[1]
        channel_count = shape[2] if len(shape) == 3 else 1
    else:
        h, w, channel_count = 100, 100, 1

    ratio        = w / max(h, 1)
    aspect_ratio = ratio / (ratio + 1)
    channel_norm = (channel_count - 1) / 3.0
    total_pixels = h * w
    size_cat     = 0.0 if total_pixels < 128*1024 else (0.5 if total_pixels < 512*1024 else 1.0)

    return [
        float(mean_orig)    / 255.0,
        float(std_orig)     / 128.0,
        float(entropy_orig) / 8.0,
        aspect_ratio, channel_norm, size_cat,
    ]


def train_model(records: list) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import LabelEncoder

    groups: dict = {}
    for rec in records:
        algo = rec.get('algorithm', '')
        if algo not in ALGO_LABELS:
            continue
        orig_id  = rec.get('original_image_id', '')
        score    = rec.get('security_score', 0)
        features = _extract_features_from_record(rec)
        if features is None:
            continue
        if orig_id not in groups:
            groups[orig_id] = {'best_algo': algo, 'best_score': score, 'features': features}
        elif score > groups[orig_id]['best_score']:
            groups[orig_id] = {'best_algo': algo, 'best_score': score, 'features': features}

    if len(groups) < MIN_SAMPLES:
        return {
            "success":      False,
            "message":      f"训练数据不足，当前 {len(groups)} 条（至少需要 {MIN_SAMPLES} 条）。",
            "sample_count": len(groups),
        }

    X     = np.array([v['features']  for v in groups.values()])
    y_raw = [v['best_algo'] for v in groups.values()]

    le  = LabelEncoder()
    y   = le.fit_transform(y_raw)

    clf = RandomForestClassifier(
        n_estimators=120, max_depth=6,
        min_samples_split=2, random_state=42, class_weight='balanced',
    )
    cv_folds  = 3 if len(groups) < 30 else 5
    cv_scores = cross_val_score(clf, X, y, cv=cv_folds, scoring='accuracy')
    accuracy  = float(np.mean(cv_scores))

    clf.fit(X, y)

    feature_names = ['mean_pixel','std_pixel','entropy_orig','aspect_ratio','channel','size']
    importance    = {n: round(float(v), 4) for n, v in zip(feature_names, clf.feature_importances_)}

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump({'clf': clf, 'le': le}, f)

    logger.info(f"Recommender trained: {len(groups)} samples, CV acc={accuracy:.3f}")
    return {
        "success":            True,
        "message":            f"模型训练成功，{len(groups)} 条样本，{cv_folds} 折交叉验证准确率 {accuracy:.1%}",
        "sample_count":       len(groups),
        "accuracy":           round(accuracy, 4),
        "feature_importance": importance,
    }


def predict(image: np.ndarray) -> dict:
    if not os.path.exists(MODEL_PATH):
        return {
            "model_exists":    False,
            "recommendations": [],
            "message":         "模型尚未训练，请先在数据大屏点击「训练推荐模型」。",
        }
    with open(MODEL_PATH, 'rb') as f:
        payload = pickle.load(f)
    clf, le = payload['clf'], payload['le']

    features = extract_image_features(image)
    proba    = clf.predict_proba(np.array([features]))[0]
    classes  = le.inverse_transform(np.arange(len(proba)))
    ranked   = sorted(zip(classes, proba), key=lambda x: x[1], reverse=True)

    recommendations = [
        {"algorithm": a, "confidence": round(float(c), 4), "rank": i+1}
        for i, (a, c) in enumerate(ranked)
    ]
    feature_names = ['mean_pixel','std_pixel','entropy_orig','aspect_ratio','channel','size']
    return {
        "model_exists":    True,
        "recommendations": recommendations,
        "features":        {n: round(v, 4) for n, v in zip(feature_names, features)},
    }


def model_exists() -> bool:
    return os.path.exists(MODEL_PATH)
