# backend/core_logic/xxtea_encryption.py
import numpy as np
import struct
import hashlib
import logging

logger = logging.getLogger(__name__)

class XXTEAEncryption:
    """XXTEA加密"""
    def __init__(self, key_string):
        self.key = self._key_to_uint32(key_string)
        self.DELTA = 0x9E3779B9
    
    def _key_to_uint32(self, key_string):
        """密钥转换，确保为4个32位整数"""
        key_bytes = key_string.encode('utf-8')
        # 使用哈希确保密钥长度一致且具有一定的随机性，然后截断或填充到16字节
        hashed_key = hashlib.sha256(key_bytes).digest()[:16]
        return struct.unpack('<4I', hashed_key)
    
    def encrypt(self, data):
        """XXTEA加密数据"""
        if not isinstance(data, bytes):
            data = data.tobytes() # 假设传入的是numpy数组的bytes
        
        if len(data) == 0:
            return b''
        
        # 填充数据到4字节的倍数
        data_len = len(data)
        padding = (4 - data_len % 4) % 4
        data_padded = data + b'\0' * padding
        
        v = list(struct.unpack('<' + 'I' * (len(data_padded) // 4), data_padded))
        n = len(v)
        
        if n < 2:
            return data # XXTEA要求至少两个32位块
        
        rounds = 6 + 52 // n
        sum_val = 0
        z = v[n-1]
        
        for _ in range(rounds):
            sum_val = (sum_val + self.DELTA) & 0xFFFFFFFF
            e = (sum_val >> 2) & 3
            for p in range(n-1):
                y = v[p+1]
                v[p] = (v[p] + self._mx(sum_val, y, z, p, e)) & 0xFFFFFFFF
                z = v[p]
            y = v[0]
            v[n-1] = (v[n-1] + self._mx(sum_val, y, z, n-1, e)) & 0xFFFFFFFF
            z = v[n-1]
        
        encrypted = struct.pack('<' + 'I' * n, *v)
        return encrypted[:data_len]  # 返回原始长度的数据

    def decrypt(self, data):
        """XXTEA解密数据"""
        if not isinstance(data, bytes):
            data = data.tobytes()
        
        if len(data) == 0:
            return b''
        
        data_len = len(data)
        padding = (4 - data_len % 4) % 4
        data_padded = data + b'\0' * padding
        
        v = list(struct.unpack('<' + 'I' * (len(data_padded) // 4), data_padded))
        n = len(v)
        
        if n < 2:
            return data
        
        rounds = 6 + 52 // n
        sum_val = (rounds * self.DELTA) & 0xFFFFFFFF
        y = v[0]
        
        for _ in range(rounds):
            e = (sum_val >> 2) & 3
            for p in range(n-1, 0, -1):
                z = v[p-1]
                v[p] = (v[p] - self._mx(sum_val, y, z, p, e)) & 0xFFFFFFFF
                y = v[p]
            z = v[n-1]
            v[0] = (v[0] - self._mx(sum_val, y, z, 0, e)) & 0xFFFFFFFF
            y = v[0]
            sum_val = (sum_val - self.DELTA) & 0xFFFFFFFF
        
        decrypted = struct.pack('<' + 'I' * n, *v)
        return decrypted[:data_len]  # 返回原始长度的数据
    
    def _mx(self, sum_val, y, z, p, e):
        """XXTEA混合函数"""
        return (((z >> 5 ^ y << 2) + (y >> 3 ^ z << 4)) ^ 
                ((sum_val ^ y) + (self.key[(p & 3) ^ e] ^ z))) & 0xFFFFFFFF
    
    def encrypt_image(self, image):
        """加密图像"""
        try:
            h, w = image.shape[:2]
            if len(image.shape) == 3:
                c = image.shape[2]
                data_bytes = image.tobytes()
                encrypted_bytes = self.encrypt(data_bytes)
                
                # 确保字节长度匹配
                expected_length = h * w * c
                if len(encrypted_bytes) < expected_length:
                    encrypted_bytes = encrypted_bytes + b'\0' * (expected_length - len(encrypted_bytes))
                elif len(encrypted_bytes) > expected_length:
                    encrypted_bytes = encrypted_bytes[:expected_length]
                    
                encrypted = np.frombuffer(encrypted_bytes, dtype=np.uint8).reshape(h, w, c)
            else: # 灰度图
                data_bytes = image.tobytes()
                encrypted_bytes = self.encrypt(data_bytes)
                
                expected_length = h * w
                if len(encrypted_bytes) < expected_length:
                    encrypted_bytes = encrypted_bytes + b'\0' * (expected_length - len(encrypted_bytes))
                elif len(encrypted_bytes) > expected_length:
                    encrypted_bytes = encrypted_bytes[:expected_length]
                    
                encrypted = np.frombuffer(encrypted_bytes, dtype=np.uint8).reshape(h, w)
            return encrypted
        except Exception as e:
            logger.error(f"XXTEA图像加密失败: {str(e)}")
            raise
    
    def decrypt_image(self, encrypted_image):
        """解密图像"""
        try:
            h, w = encrypted_image.shape[:2]
            if len(encrypted_image.shape) == 3:
                c = encrypted_image.shape[2]
                data_bytes = encrypted_image.tobytes()
                decrypted_bytes = self.decrypt(data_bytes)
                
                expected_length = h * w * c
                if len(decrypted_bytes) < expected_length:
                    decrypted_bytes = decrypted_bytes + b'\0' * (expected_length - len(decrypted_bytes))
                elif len(decrypted_bytes) > expected_length:
                    decrypted_bytes = decrypted_bytes[:expected_length]
                    
                decrypted = np.frombuffer(decrypted_bytes, dtype=np.uint8).reshape(h, w, c)
            else: # 灰度图
                data_bytes = encrypted_image.tobytes()
                decrypted_bytes = self.decrypt(data_bytes)
                
                expected_length = h * w
                if len(decrypted_bytes) < expected_length:
                    decrypted_bytes = decrypted_bytes + b'\0' * (expected_length - len(decrypted_bytes))
                elif len(decrypted_bytes) > expected_length:
                    decrypted_bytes = decrypted_bytes[:expected_length]
                    
                decrypted = np.frombuffer(decrypted_bytes, dtype=np.uint8).reshape(h, w)
            return decrypted
        except Exception as e:
            logger.error(f"XXTEA图像解密失败: {str(e)}")
            raise