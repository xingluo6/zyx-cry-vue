# backend/config.py
import os

# 获取项目根目录 (假设backend在项目根目录下)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 临时图片存储目录
TEMP_IMAGES_FOLDER = os.path.join(BASE_DIR, 'temp_images')
# 确保目录存在
os.makedirs(TEMP_IMAGES_FOLDER, exist_ok=True)

# 允许上传的图片文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff'}

# Flask应用密钥 (用于会话管理等，这里只是一个占位符)
SECRET_KEY = os.environ.get('SECRET_KEY') or 'a_very_secret_key_for_flask_app'

# 图像文件ID到文件路径和形状的映射 (简单起见，使用内存字典)
# 在生产环境中，这应该是一个数据库或更持久的存储
IMAGE_STORE = {}