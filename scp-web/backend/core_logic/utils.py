# backend/core_logic/utils.py
import os
import cv2
import numpy as np
import base64
import hashlib
import json # 用于序列化/反序列化 CombinedEncryption 的状态
import logging

# 设置日志输出
logger = logging.getLogger(__name__)

# 尝试导入AES相关库，以便CombinedEncryption和AESEncryption类能正常工作
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Random import get_random_bytes
    AES_AVAILABLE = True
except ImportError:
    AES_AVAILABLE = False
    logger.warning("警告: PyCryptodome库未安装，AES加密功能不可用")
    logger.warning("请使用: pip install pycryptodome 安装")

# 从其他文件导入加密器类
from .arnold_encryption import ArnoldEncryption
from .xor_encryption import XOREncryption
from .xxtea_encryption import XXTEAEncryption
from .aes_encryption import AESEncryption
from .logistic_chaotic_encryption import LogisticChaoticEncryption


def load_image_safe(file_path):
    """安全加载图像"""
    try:
        # 优先使用OpenCV加载，因为它在处理各种图像格式方面通常更稳定
        # IMREAD_UNCHANGED 确保加载所有通道，包括alpha
        image_array = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)

        if image_array is None:
            logger.error(f"OpenCV无法加载图像: {file_path}")
            return None
        
        # 如果是单通道灰度图，确保其形状是 (H, W) 而不是 (H, W, 1)
        if len(image_array.shape) == 3 and image_array.shape[2] == 1:
            image_array = image_array.squeeze()

        # OpenCV默认是BGR/BGRA，通常无需转换为RGB/RGBA，直接使用即可
        return image_array
    except Exception as e:
        logger.error(f"加载图像失败: {e}")
    return None

def save_image_safe(image_array, file_path):
    """安全保存图像"""
    try:
        if image_array is None:
            raise ValueError("图像数据为None，无法保存。")
        success = cv2.imwrite(file_path, image_array)
        if not success:
            raise IOError(f"OpenCV无法保存图像到 {file_path}")
        return True
    except Exception as e:
        logger.error(f"保存图像失败: {e}")
        return False

def image_to_base64(image_array, format=".png"):
    """将numpy图像数组转换为Base64编码的字符串"""
    if image_array is None:
        return None
    
    # 尝试将图像编码为指定格式的字节流
    # 根据图像通道数选择编码格式
    if len(image_array.shape) == 3 and image_array.shape[2] == 4: # BGRA
        is_success, buffer = cv2.imencode(format, image_array)
    elif len(image_array.shape) == 3 and image_array.shape[2] == 3: # BGR
        is_success, buffer = cv2.imencode(format, image_array)
    elif len(image_array.shape) == 2: # Grayscale
        is_success, buffer = cv2.imencode(format, image_array)
    else:
        logger.error(f"不支持的图像形状: {image_array.shape}")
        return None

    if not is_success:
        logger.error(f"图像编码为{format}失败")
        return None
    
    # 将字节流转换为Base64字符串
    return base64.b64encode(buffer).decode("utf-8")

def base64_to_image(base64_string):
    """将Base64编码的字符串解码为numpy图像数组"""
    if base64_string is None:
        return None
    
    try:
        # 解码Base64字符串为字节流
        img_bytes = base64.b64decode(base64_string)
        # 将字节流转换为numpy数组
        img_array = np.frombuffer(img_bytes, np.uint8)
        # 使用OpenCV解码图像
        image = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
        
        if image is None:
            raise ValueError("Base64字符串解码为图像失败")

        # 如果是单通道灰度图，确保其形状是 (H, W) 而不是 (H, W, 1)
        if len(image.shape) == 3 and image.shape[2] == 1:
            image = image.squeeze()

        return image
    except Exception as e:
        logger.error(f"Base64解码图像失败: {e}")
        return None

def generate_key_from_filename(filename):
    """根据文件名生成密钥 (此函数在Web后端可能不直接使用，因为文件上传后通常是临时ID)"""
    name_without_ext = os.path.splitext(os.path.basename(filename))[0]
    if not name_without_ext:
        return "default_key_123456"
    # 使用哈希确保密钥长度一致且具有一定的随机性
    return hashlib.sha256(name_without_ext.encode('utf-8')).hexdigest()[:16]

# ============================ 修复的组合加密算法 ============================

class CombinedEncryption:
    """组合加密算法"""
    def __init__(self):
        self.encryptors = [] # 存储加密器实例
        self.params = []     # 存储每个加密器对应的原始参数
        self.encryptor_states = []  # 存储每个加密器的状态 (如Arnold的padding_info, Logistic的r/x0)
        self.original_image_shape = None # 存储原始图像形状，用于最终裁剪

    def add_algorithm(self, algorithm_name, params):
        """
        根据算法名称和参数添加加密算法实例到链中。
        algorithm_name: 字符串，如 "Arnold", "XOR", "XXTEA", "AES", "Logistic"
        params: 字典，该算法的特定参数
        """
        # 根据名称创建实例
        if algorithm_name == "Arnold":
            encryptor = ArnoldEncryption()
        elif algorithm_name == "XOR":
            encryptor = XOREncryption(
                key_string=params.get('key', 'combined_xor_key'),
                xor_mode=params.get('xor_mode', 'string'),
                xor_byte=params.get('xor_byte', 0x17)
            )
        elif algorithm_name == "XXTEA":
            encryptor = XXTEAEncryption(key_string=params.get('key', 'combined_xxtea_key'))
        elif algorithm_name == "AES":
            if not AES_AVAILABLE:
                raise ImportError("PyCryptodome库未安装，AES加密功能不可用")
            encryptor = AESEncryption(
                key=params.get('key', 'combined_aes_key_123'),
                mode=params.get('mode', 'CFB')
            )
        elif algorithm_name == "Logistic":
            encryptor = LogisticChaoticEncryption(
                key_string=params.get('key_string', 'combined_logistic_key'),
                r=params.get('r', 3.99),
                x0=params.get('x0', 0.01),
                discard_iterations=params.get('discard_iterations', 100)
            )
        else:
            raise ValueError(f"不支持的加密算法: {algorithm_name}")

        self.encryptors.append(encryptor)
        self.params.append(params) # 存储原始参数，在解密时可能需要

    def encrypt(self, image):
        """执行组合加密"""
        self.original_image_shape = image.shape
        self.encryptor_states = []  # 重置状态列表
        
        result = image.copy()
        for i, encryptor_instance in enumerate(self.encryptors):
            algo_name = encryptor_instance.__class__.__name__.replace("Encryption", "")
            logger.info(f"组合加密步骤 {i+1}: {algo_name}")
            
            current_params = self.params[i] # 获取当前算法的参数

            if isinstance(encryptor_instance, ArnoldEncryption):
                iterations = current_params.get('iterations', 10)
                # Arnold加密会返回填充后的图像和padding_info
                result, padding_info = encryptor_instance._arnold_transform_square(result, iterations)
                # ArnoldEncryptor的state需要padding_info和original_shape
                self.encryptor_states.append({
                    'original_shape': self.original_image_shape, # 记录原始图像的形状
                    'padding_info': padding_info # 存储_arnold_transform_square返回的padding_info
                })
                
            elif isinstance(encryptor_instance, XOREncryption):
                result = encryptor_instance.encrypt(result)
                self.encryptor_states.append(None) # XOR不需要保存状态
                
            elif isinstance(encryptor_instance, XXTEAEncryption):
                result = encryptor_instance.encrypt_image(result)
                self.encryptor_states.append(None) # XXTEA不需要保存状态
                
            elif isinstance(encryptor_instance, AESEncryption):
                result = encryptor_instance.encrypt(result)
                self.encryptor_states.append(None) # AES不需要保存状态
                
            elif isinstance(encryptor_instance, LogisticChaoticEncryption):
                use_key_params = current_params.get('use_key_params', True)
                result = encryptor_instance.encrypt(result, use_key_params=use_key_params)
                self.encryptor_states.append(encryptor_instance.get_state()) # Logistic需要保存状态
                
            else:
                raise ValueError(f"不支持的加密算法: {type(encryptor_instance)}")
            
            logger.info(f"步骤 {i+1} 后图像尺寸: {result.shape}")
        
        return result
    
    def decrypt(self, image):
        """执行组合解密"""
        if not self.encryptor_states or len(self.encryptors) != len(self.encryptor_states):
            logger.error("加密器状态信息不完整或与算法链不匹配，无法正确解密")
            raise ValueError("加密器状态信息不完整，无法正确解密。请确保加密和解密使用相同的CombinedEncryption实例或其完整状态。")
        
        result = image.copy()
        
        # 反向解密
        for i, encryptor_instance in enumerate(reversed(self.encryptors)):
            step_index = len(self.encryptors) - i - 1 # 获取当前反向步骤对应的原始正向步骤索引
            algo_name = encryptor_instance.__class__.__name__.replace("Encryption", "")
            logger.info(f"组合解密步骤 {i+1} (反向): {algo_name}")
            
            current_params = self.params[step_index] # 获取当前算法的原始参数
            state = self.encryptor_states[step_index] # 获取对应步骤的保存状态
            
            # 恢复加密器状态
            if state and hasattr(encryptor_instance, 'set_state'):
                encryptor_instance.set_state(state)
                logger.debug(f"恢复 {algo_name} 状态")
            
            if isinstance(encryptor_instance, ArnoldEncryption):
                iterations = current_params.get('iterations', 10)
                result_before = result.shape
                result = encryptor_instance.decrypt(result, iterations)
                result_after = result.shape
                logger.debug(f"Arnold解密尺寸变化: {result_before} -> {result_after}")
                
                # 强制裁剪回原始图像的原始尺寸（双重保障）
                if self.original_image_shape is not None:
                    original_h, original_w = self.original_image_shape[:2]
                    current_h, current_w = result.shape[:2]
                    
                    if len(result.shape) == 3: # 彩色图像
                        if (original_h, original_w) != (current_h, current_w):
                            logger.info(f"强制裁剪: {current_w}x{current_h} -> {original_w}x{original_h}")
                            result = result[:original_h, :original_w, :]
                    else: # 灰度图像
                        if (original_h, original_w) != (current_h, current_w):
                            logger.info(f"强制裁剪: {current_w}x{current_h} -> {original_w}x{original_h}")
                            result = result[:original_h, :original_w]
                
            elif isinstance(encryptor_instance, XOREncryption):
                result = encryptor_instance.decrypt(result)
                
            elif isinstance(encryptor_instance, XXTEAEncryption):
                result = encryptor_instance.decrypt_image(result)
                
            elif isinstance(encryptor_instance, AESEncryption):
                result = encryptor_instance.decrypt(result)
                
            elif isinstance(encryptor_instance, LogisticChaoticEncryption):
                use_key_params = current_params.get('use_key_params', True)
                result = encryptor_instance.decrypt(result, use_key_params=use_key_params)
                
            else:
                raise ValueError(f"不支持的加密算法: {type(encryptor_instance)}")
            
            logger.debug(f"步骤 {i+1} 后图像尺寸: {result.shape}")
        
        return result

    def get_state(self):
        """
        获取整个CombinedEncryption实例的状态，用于序列化。
        这包括加密器链的类型、参数和内部状态，以及原始图像形状。
        """
        # 序列化encryptors列表，只存储它们的类型名称和原始参数
        encryptor_info = [
            {"name": e.__class__.__name__.replace("Encryption", ""), "params": p}
            for e, p in zip(self.encryptors, self.params)
        ]
        
        return {
            'encryptor_states': self.encryptor_states,
            'original_image_shape': self.original_image_shape,
            'encryptor_info': encryptor_info
        }
    
    @classmethod
    def from_state(cls, state):
        """
        从序列化的状态字典重新创建CombinedEncryption实例。
        """
        instance = cls()
        instance.encryptor_states = state.get('encryptor_states', [])
        instance.original_image_shape = state.get('original_image_shape')
        
        # 从存储的加密器信息中重新构建encryptors列表
        encryptor_info = state.get('encryptor_info', [])
        for info in encryptor_info:
            instance.add_algorithm(info['name'], info['params']) # 使用add_algorithm来重新实例化
            
        return instance