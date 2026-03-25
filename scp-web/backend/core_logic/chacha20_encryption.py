# backend/core_logic/chacha20_encryption.py
"""
ChaCha20-Poly1305 加密（Google 推动的现代流密码）。

与 AES 的区别：
  - 流密码，无需分块填充，天然适合变长数据
  - 无需硬件加速即可达到 AES-NI 同等速度，移动端性能更优
  - Poly1305 提供 MAC 认证，安全性等同于 AES-GCM
  - TLS 1.3 标准算法之一（RFC 8439），被 Android/iOS/Chrome 广泛使用
  - 对 timing-attack 更鲁棒（不依赖 S-box 查表）
"""
import os
import hashlib
import numpy as np
import logging

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

logger = logging.getLogger(__name__)


class ChaCha20Encryption:
    """ChaCha20-Poly1305 图像加密"""

    # ChaCha20-Poly1305 标准 nonce：96 bit = 12 字节
    NONCE_SIZE = 12

    def __init__(self, key_string: str = 'default_chacha20_key'):
        self.key_string = key_string
        self.key        = self._derive_key(key_string)

    def _derive_key(self, key_string: str) -> bytes:
        """从字符串派生 32 字节（256-bit）密钥"""
        return hashlib.sha256(key_string.encode('utf-8')).digest()

    def encrypt(self, image: np.ndarray) -> np.ndarray:
        """
        ChaCha20-Poly1305 加密。
        输出结构：nonce(12B) + ciphertext+tag（tag 内嵌在末尾 16B）
        """
        try:
            original_shape = image.shape
            image_bytes    = image.tobytes()

            chacha  = ChaCha20Poly1305(self.key)
            nonce   = os.urandom(self.NONCE_SIZE)

            # encrypt 返回 ciphertext + 16字节 Poly1305 tag
            encrypted_bytes = chacha.encrypt(nonce, image_bytes, None)
            combined        = nonce + encrypted_bytes

            return self._bytes_to_image(combined, original_shape)

        except Exception as e:
            logger.error(f"ChaCha20 加密失败: {e}")
            raise

    def decrypt(self, encrypted_image: np.ndarray) -> np.ndarray:
        """ChaCha20-Poly1305 解密并验证完整性"""
        try:
            original_shape  = encrypted_image.shape
            encrypted_bytes = encrypted_image.tobytes()

            if len(encrypted_bytes) < self.NONCE_SIZE + 16:
                raise ValueError("加密数据太短")

            nonce          = encrypted_bytes[:self.NONCE_SIZE]
            actual_payload = encrypted_bytes[self.NONCE_SIZE:]

            chacha = ChaCha20Poly1305(self.key)
            decrypted_bytes = chacha.decrypt(nonce, actual_payload, None)

            return self._bytes_to_image(decrypted_bytes, original_shape)

        except Exception as e:
            logger.error(f"ChaCha20 解密失败: {e}")
            raise

    @staticmethod
    def _bytes_to_image(data: bytes, original_shape: tuple) -> np.ndarray:
        arr   = np.frombuffer(data, dtype=np.uint8)
        total = int(np.prod(original_shape))
        if len(arr) > total:
            arr = arr[:total]
        elif len(arr) < total:
            arr = np.concatenate([arr, np.zeros(total - len(arr), dtype=np.uint8)])
        return arr.reshape(original_shape)
