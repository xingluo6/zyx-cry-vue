# backend/core_logic/aes_encryption.py
import numpy as np
import logging

# 尝试导入AES相关库
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Random import get_random_bytes
    AES_AVAILABLE = True
except ImportError:
    AES_AVAILABLE = False

logger = logging.getLogger(__name__)

class AESEncryption:
    """AES加密算法"""
    def __init__(self, key, mode='CFB'):
        if not AES_AVAILABLE:
            raise ImportError("PyCryptodome库未安装，AES加密功能不可用。请安装: pip install pycryptodome")
        self.key = self._process_key(key)
        self.mode = mode
        self.iv = None
        
    def _process_key(self, key):
        """处理密钥，确保为16, 24或32字节"""
        if isinstance(key, str):
            key = key.encode('utf-8')
        
        # 根据密钥长度调整
        if len(key) < 16:
            key = key.ljust(16, b'\0')
        elif len(key) < 24:
            key = key.ljust(24, b'\0')
        elif len(key) < 32:
            key = key.ljust(32, b'\0')
        else:
            key = key[:32] # 截断到32字节
            
        return key
    
    def encrypt(self, image):
        """AES加密图像"""
        try:
            original_shape = image.shape
            image_bytes = image.tobytes()
            
            # 生成随机IV（对于需要IV的模式）
            if self.mode in ['CBC', 'CFB', 'OFB']:
                self.iv = get_random_bytes(16)
            
            # 创建AES加密器
            if self.mode == 'ECB':
                cipher = AES.new(self.key, AES.MODE_ECB)
                padded_data = pad(image_bytes, AES.block_size)
                encrypted_bytes = cipher.encrypt(padded_data)
                
            elif self.mode == 'CBC':
                cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
                padded_data = pad(image_bytes, AES.block_size)
                encrypted_bytes = cipher.encrypt(padded_data)
                
            elif self.mode == 'CFB':
                cipher = AES.new(self.key, AES.MODE_CFB, self.iv, segment_size=128)
                encrypted_bytes = cipher.encrypt(image_bytes)
                
            elif self.mode == 'OFB':
                cipher = AES.new(self.key, AES.MODE_OFB, self.iv)
                encrypted_bytes = cipher.encrypt(image_bytes)
            else:
                raise ValueError(f"不支持的AES模式: {self.mode}")
            
            # 对于需要IV的模式，将IV和加密数据组合
            if self.mode in ['CBC', 'CFB', 'OFB']:
                combined_data = self.iv + encrypted_bytes
            else:
                combined_data = encrypted_bytes
            
            # 将加密后的字节转换回图像
            # 注意：加密后的数据长度可能与原始数据不同，因此需要调整形状
            encrypted_image = np.frombuffer(combined_data, dtype=np.uint8)
            
            # 调整形状以匹配原始图像
            # 计算新形状，保持通道数不变
            if len(original_shape) == 3:
                h, w, c = original_shape
                total_pixels = h * w * c
            else:
                h, w = original_shape
                c = 1
                total_pixels = h * w
            
            # 调整加密数据长度以匹配图像形状
            if len(encrypted_image) > total_pixels:
                encrypted_image = encrypted_image[:total_pixels]
            elif len(encrypted_image) < total_pixels:
                temp = np.zeros(total_pixels, dtype=np.uint8)
                temp[:len(encrypted_image)] = encrypted_image
                encrypted_image = temp
            
            # 重塑为图像形状
            if len(original_shape) == 3:
                encrypted_image = encrypted_image.reshape(h, w, c)
            else:
                encrypted_image = encrypted_image.reshape(h, w)
                
            return encrypted_image
            
        except Exception as e:
            logger.error(f"AES加密失败: {str(e)}")
            raise
    
    def decrypt(self, encrypted_image):
        """AES解密图像"""
        try:
            original_shape = encrypted_image.shape
            encrypted_bytes = encrypted_image.tobytes()
            
            # 对于需要IV的模式，从加密数据中提取IV
            if self.mode in ['CBC', 'CFB', 'OFB']:
                if len(encrypted_bytes) < 16:
                    raise ValueError("加密数据太短，无法提取IV")
                
                self.iv = encrypted_bytes[:16]
                actual_encrypted_bytes = encrypted_bytes[16:]
            else:
                actual_encrypted_bytes = encrypted_bytes
            
            # 创建AES解密器
            if self.mode == 'ECB':
                cipher = AES.new(self.key, AES.MODE_ECB)
                decrypted_bytes = cipher.decrypt(actual_encrypted_bytes)
                try:
                    decrypted_bytes = unpad(decrypted_bytes, AES.block_size)
                except ValueError as e:
                    logger.warning(f"ECB解密去除填充失败: {str(e)}，可能数据已被截断或密钥错误。")
                    
            elif self.mode == 'CBC':
                if self.iv is None:
                    raise ValueError("CBC模式需要IV")
                cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
                decrypted_bytes = cipher.decrypt(actual_encrypted_bytes)
                try:
                    decrypted_bytes = unpad(decrypted_bytes, AES.block_size)
                except ValueError as e:
                    logger.warning(f"CBC解密去除填充失败: {str(e)}，可能数据已被截断或密钥错误。")
                    
            elif self.mode == 'CFB':
                if self.iv is None:
                    raise ValueError("CFB模式需要IV")
                cipher = AES.new(self.key, AES.MODE_CFB, self.iv, segment_size=128)
                decrypted_bytes = cipher.decrypt(actual_encrypted_bytes)
                
            elif self.mode == 'OFB':
                if self.iv is None:
                    raise ValueError("OFB模式需要IV")
                cipher = AES.new(self.key, AES.MODE_OFB, self.iv)
                decrypted_bytes = cipher.decrypt(actual_encrypted_bytes)
            else:
                raise ValueError(f"不支持的AES模式: {self.mode}")
            
            # 将解密后的字节转换回图像
            decrypted_image = np.frombuffer(decrypted_bytes, dtype=np.uint8)
            
            # 调整形状以匹配原始图像
            if len(original_shape) == 3:
                h, w, c = original_shape
                total_pixels = h * w * c
            else:
                h, w = original_shape
                c = 1
                total_pixels = h * w
            
            if len(decrypted_image) > total_pixels:
                decrypted_image = decrypted_image[:total_pixels]
            elif len(decrypted_image) < total_pixels:
                temp = np.zeros(total_pixels, dtype=np.uint8)
                temp[:len(decrypted_image)] = decrypted_image
                decrypted_image = temp
            
            if len(original_shape) == 3:
                decrypted_image = decrypted_image.reshape(h, w, c)
            else:
                decrypted_image = decrypted_image.reshape(h, w)
                
            return decrypted_image
            
        except Exception as e:
            logger.error(f"AES解密失败: {str(e)}")
            raise