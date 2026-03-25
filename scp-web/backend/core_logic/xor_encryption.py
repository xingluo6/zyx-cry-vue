# backend/core_logic/xor_encryption.py
import numpy as np
import hashlib
import logging

logger = logging.getLogger(__name__)

class XOREncryption:
    """XOR加密"""
    def __init__(self, key_string, xor_mode="string", xor_byte=0x17):
        self.key_string = key_string
        self.xor_mode = xor_mode
        self.xor_byte = xor_byte
    
    def _generate_key_stream(self, data_length):
        """生成密钥流"""
        if self.xor_mode == "byte":
            return bytearray([self.xor_byte] * data_length)
        else:
            key_bytes = self.key_string.encode('utf-8')
            key_length = len(key_bytes)
            return bytearray([key_bytes[i % key_length] for i in range(data_length)])
    
    def encrypt(self, image):
        """XOR加密"""
        return self._process_image(image)
    
    def _process_image(self, image):
        """加密/解密图像数据"""
        if len(image.shape) == 3:
            h, w, c = image.shape
            if c == 4: # RGBA图像
                rgb_image = image[:, :, :3]
                alpha_channel = image[:, :, 3]
                processed_rgb = self._process_channels(rgb_image)
                processed_alpha = self._process_grayscale_channel(alpha_channel)
                processed = np.dstack((processed_rgb, processed_alpha))
            else: # RGB/BGR图像
                processed = self._process_channels(image)
        else: # 灰度图像
            processed = self._process_grayscale_channel(image)
        return processed.astype(np.uint8)

    def _process_channels(self, image):
        """处理彩色图像的每个通道"""
        h, w, c = image.shape
        processed_channels = []
        for channel in range(c):
            channel_data = image[:, :, channel].flatten()
            key_stream = self._generate_key_stream(len(channel_data))
            processed_channel = np.bitwise_xor(channel_data, key_stream)
            processed_channels.append(processed_channel.reshape((h, w)))
        return np.stack(processed_channels, axis=2)

    def _process_grayscale_channel(self, image):
        """处理灰度图像或单个通道"""
        h, w = image.shape
        flattened = image.flatten()
        key_stream = self._generate_key_stream(len(flattened))
        processed_flat = np.bitwise_xor(flattened, key_stream)
        return processed_flat.reshape((h, w))

    def decrypt(self, encrypted_image):
        """XOR解密 (与加密过程相同，因为XOR是自逆运算)"""
        return self._process_image(encrypted_image)