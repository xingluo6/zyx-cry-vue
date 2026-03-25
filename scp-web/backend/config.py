# backend/config.py
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 临时图片存储目录
TEMP_IMAGES_FOLDER = os.path.join(BASE_DIR, 'temp_images')
os.makedirs(TEMP_IMAGES_FOLDER, exist_ok=True)

# 允许上传的图片文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}

# Flask 密钥
SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_very_secret_key_for_flask_app'

# ──────────────────────────────────────────────
# MongoDB 配置
# ──────────────────────────────────────────────
# 本地开发直接用默认地址，生产环境可通过环境变量覆盖
MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/'
MONGO_DB_NAME = 'image_crypto_db'

# 集合名称常量，统一管理避免拼写错误
COLLECTION_IMAGES    = 'images'      # 存储上传/加密图像的元信息
COLLECTION_ANALYSIS  = 'analysis'    # 存储每次分析结果（核心数据）

# ──────────────────────────────────────────────
# 兼容旧代码：IMAGE_STORE 不再使用，改为 MongoDB
# 保留此注释作为迁移说明
# IMAGE_STORE = {}   ← 已移除，请使用 database.py 中的函数
# ──────────────────────────────────────────────