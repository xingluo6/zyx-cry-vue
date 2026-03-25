# backend/core_logic/logistic_chaotic_encryption.py
import numpy as np
import hashlib
import logging

logger = logging.getLogger(__name__)

class LogisticChaoticEncryption:
    """Logistic混沌加密"""
    def __init__(self, key_string="default_logistic_key", r=3.99, x0=0.01, discard_iterations=100):
        self.key_string = key_string
        self.r = r
        self.x0 = x0
        self.discard_iterations = discard_iterations # 丢弃前N次迭代，避免瞬态效应
        self.generated_r = None # 存储实际使用的r值
        self.generated_x0 = None # 存储实际使用的x0值
        self.key_stream_length = 0 # 存储密钥流长度，用于解密时生成相同长度的流

    def _derive_params_from_key(self):
        """从密钥字符串派生r和x0"""
        hash_val = hashlib.sha256(self.key_string.encode('utf-8')).hexdigest()
        
        # 从哈希值中提取部分作为整数
        int_val1 = int(hash_val[0:8], 16) # 前8位十六进制
        int_val2 = int(hash_val[8:16], 16) # 后8位十六进制

        # 派生r: 确保 r 在 (3.57, 4.0] 范围内
        # (int_val1 % 43000) / 100000.0 会生成 (0, 0.43) 范围的浮点数
        # 加上 3.57 确保 r 在 (3.57, 4.0]
        derived_r = 3.57 + (int_val1 % 43000) / 100000.0
        
        # 派生x0: 确保 x0 在 (0, 1) 范围内，且不为0或1
        # (int_val2 % 998) / 1000.0 会生成 (0, 0.998) 范围的浮点数
        # 加上 0.001 确保 x0 在 (0.001, 0.999) 范围内
        derived_x0 = (int_val2 % 998) / 1000.0 + 0.001

        self.generated_r = derived_r
        self.generated_x0 = derived_x0
        logger.debug(f"从密钥 '{self.key_string}' 派生参数: r={self.generated_r:.6f}, x0={self.generated_x0:.6f}")

    def _generate_chaotic_sequence(self, length):
        """生成Logistic混沌序列作为密钥流"""
        r_val = self.r if self.generated_r is None else self.generated_r
        x_val = self.x0 if self.generated_x0 is None else self.generated_x0

        if not (3.57 < r_val <= 4.0):
            raise ValueError(f"Logistic参数r必须在(3.57, 4.0]范围内，当前r={r_val}")
        if not (0 < x_val < 1):
            raise ValueError(f"Logistic初始值x0必须在(0, 1)范围内，当前x0={x_val}")

        # 预热迭代，丢弃前N次迭代，避免瞬态效应
        current_x = x_val
        for _ in range(self.discard_iterations):
            current_x = r_val * current_x * (1 - current_x)
        
        # 生成实际密钥流
        chaotic_sequence = np.zeros(length, dtype=np.uint8)
        for i in range(length):
            current_x = r_val * current_x * (1 - current_x)
            # 将(0,1)范围的浮点数映射到(0,255)的整数
            chaotic_sequence[i] = int(current_x * 255)
            # 确保不出现0或255，增加随机性（可选，但有助于避免XOR 0或XOR 255的特殊情况）
            if chaotic_sequence[i] == 0:
                chaotic_sequence[i] = 1
            elif chaotic_sequence[i] == 255:
                chaotic_sequence[i] = 254
                
        return chaotic_sequence

    def encrypt(self, image, use_key_params=True):
        """Logistic混沌加密"""
        if image is None:
            raise ValueError("输入图像为None")

        if use_key_params:
            self._derive_params_from_key()
        else:
            self.generated_r = None # 清除派生参数，确保使用手动设置的r,x0
            self.generated_x0 = None

        original_shape = image.shape
        image_flat = image.flatten()
        self.key_stream_length = len(image_flat) # 记录密钥流长度
        
        # 生成与图像数据长度相同的混沌序列
        key_stream = self._generate_chaotic_sequence(self.key_stream_length)
        
        # 执行XOR操作
        encrypted_flat = np.bitwise_xor(image_flat, key_stream)
        
        return encrypted_flat.reshape(original_shape).astype(np.uint8)

    def decrypt(self, encrypted_image, use_key_params=True):
        """Logistic混沌解密 (与加密过程相同，因为XOR是自逆运算)"""
        if encrypted_image is None:
            raise ValueError("输入加密图像为None")

        if use_key_params:
            self._derive_params_from_key()
        else:
            self.generated_r = None # 清除派生参数，确保使用手动设置的r,x0
            self.generated_x0 = None
            
        original_shape = encrypted_image.shape
        encrypted_flat = encrypted_image.flatten()
        
        # 生成与图像数据长度相同的混沌序列 (必须与加密时使用的序列完全相同)
        # 优先使用加密时记录的长度，如果没有则使用当前图像的长度
        key_stream_len = self.key_stream_length if self.key_stream_length > 0 else len(encrypted_flat)
        key_stream = self._generate_chaotic_sequence(key_stream_len)
        
        # 执行XOR操作
        decrypted_flat = np.bitwise_xor(encrypted_flat, key_stream)
        
        return decrypted_flat.reshape(original_shape).astype(np.uint8)

    def get_state(self):
        """获取加密器状态，以便在组合加密中恢复"""
        return {
            'key_string': self.key_string,
            'r': self.r,
            'x0': self.x0,
            'discard_iterations': self.discard_iterations,
            'generated_r': self.generated_r,
            'generated_x0': self.generated_x0,
            'key_stream_length': self.key_stream_length
        }
    
    def set_state(self, state):
        """设置加密器状态"""
        if state:
            self.key_string = state.get('key_string', self.key_string)
            self.r = state.get('r', self.r)
            self.x0 = state.get('x0', self.x0)
            self.discard_iterations = state.get('discard_iterations', self.discard_iterations)
            self.generated_r = state.get('generated_r')
            self.generated_x0 = state.get('generated_x0')
            self.key_stream_length = state.get('key_stream_length', 0)