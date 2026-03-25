# backend/core_logic/aesgcm_encryption.py
"""
AES-GCM 加密（带完整性验证的现代模式）。

与传统 AES-CFB/CBC 的区别：
  - GCM 是 AEAD（认证加密），同时提供机密性 + 完整性保护
  - 内置认证标签（Auth Tag），可检测密文是否被篡改
  - 无需填充，是目前 TLS 1.3 / HTTPS 的默认加密模式
  - 比 CBC 更安全，比 CFB 更快（支持硬件加速）
"""
import os
import hashlib
import numpy as np
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


class AESGCMEncryption:
    """AES-256-GCM 图像加密"""

    # GCM 标准 nonce 长度：96 bit = 12 字节
    NONCE_SIZE = 12

    def __init__(self, key_string: str = 'default_aesgcm_key'):
        self.key_string = key_string
        self.key        = self._derive_key(key_string)

    def _derive_key(self, key_string: str) -> bytes:
        """从任意字符串派生 32 字节（256-bit）密钥"""
        return hashlib.sha256(key_string.encode('utf-8')).digest()

    def encrypt(self, image: np.ndarray) -> np.ndarray:
        """
        AES-GCM 加密图像。
        输出结构：nonce(12B) + auth_tag(16B，GCM 内嵌在密文末尾) + ciphertext
        为保持与原始 shape 一致，截断/填充输出数据。
        """
        try:
            original_shape = image.shape
            image_bytes    = image.tobytes()

            aesgcm = AESGCM(self.key)
            nonce  = os.urandom(self.NONCE_SIZE)

            # AESGCM.encrypt 返回 ciphertext + 16字节 auth_tag（拼接在末尾）
            encrypted_bytes = aesgcm.encrypt(nonce, image_bytes, None)

            # 拼接：nonce + encrypted_bytes（含 tag）
            combined = nonce + encrypted_bytes

            return self._bytes_to_image(combined, original_shape)

        except Exception as e:
            logger.error(f"AES-GCM 加密失败: {e}")
            raise

    def decrypt(self, encrypted_image: np.ndarray) -> np.ndarray:
        """AES-GCM 解密图像，同时验证完整性"""
        try:
            original_shape  = encrypted_image.shape
            encrypted_bytes = encrypted_image.tobytes()

            if len(encrypted_bytes) < self.NONCE_SIZE + 16:
                raise ValueError("加密数据太短，无法提取 nonce 和 tag")

            nonce          = encrypted_bytes[:self.NONCE_SIZE]
            actual_payload = encrypted_bytes[self.NONCE_SIZE:]

            aesgcm = AESGCM(self.key)

            # decrypt 会同时验证 auth_tag，篡改时抛出 InvalidTag
            decrypted_bytes = aesgcm.decrypt(nonce, actual_payload, None)

            return self._bytes_to_image(decrypted_bytes, original_shape)

        except Exception as e:
            logger.error(f"AES-GCM 解密失败: {e}")
            raise

    @staticmethod
    def _bytes_to_image(data: bytes, original_shape: tuple) -> np.ndarray:
        """将字节数据调整为目标 shape"""
        arr        = np.frombuffer(data, dtype=np.uint8)
        total      = int(np.prod(original_shape))
        if len(arr) > total:
            arr = arr[:total]
        elif len(arr) < total:
            pad = np.zeros(total - len(arr), dtype=np.uint8)
            arr = np.concatenate([arr, pad])
        return arr.reshape(original_shape)
