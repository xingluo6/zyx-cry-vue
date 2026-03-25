# backend/core_logic/arnold_encryption.py
import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)

class ArnoldEncryption:
    """Arnold猫映射加密"""
    def __init__(self):
        self.name = "Arnold Transform"
        self.original_shape = None
        self.padding_info = None  # 存储填充信息

    def encrypt(self, image, iterations=10):
        """Arnold加密 - 使用正方形填充方法，返回填充后的正方形图像"""
        if image is None:
            raise ValueError("输入图像为None")
            
        # 保存原始形状
        self.original_shape = image.shape
        
        if len(image.shape) == 3:
            h, w, c = image.shape
            if c == 4: # RGBA图像
                rgb_image = image[:, :, :3]
                alpha_channel = image[:, :, 3]
                encrypted_rgb, padding_rgb = self._arnold_transform_square(rgb_image, iterations)
                encrypted_alpha, padding_alpha = self._arnold_transform_square(alpha_channel, iterations)
                encrypted = np.dstack((encrypted_rgb, encrypted_alpha))
                self.padding_info = padding_rgb  # 使用RGB的填充信息
            else: # RGB/BGR图像
                encrypted, self.padding_info = self._arnold_transform_square(image, iterations)
        else: # 灰度图像
            encrypted, self.padding_info = self._arnold_transform_square(image, iterations)

        return encrypted.astype(np.uint8)

    def _arnold_transform_square(self, image, iterations):
        """Arnold变换 - 正方形填充方法，返回填充后的图像和填充信息"""
        if len(image.shape) == 3:
            h, w, c = image.shape
            is_color = True
        else:
            h, w = image.shape
            is_color = False
        
        # 找到最接近的2的幂次方尺寸
        N = 1
        while N < max(h, w):
            N *= 2
        
        # 计算填充尺寸（居中填充）
        pad_top = (N - h) // 2
        pad_bottom = N - h - pad_top
        pad_left = (N - w) // 2
        pad_right = N - w - pad_left
        
        logger.debug(f"原始尺寸: {h}x{w}, 填充后: {N}x{N}, 填充: ({pad_top}, {pad_bottom}, {pad_left}, {pad_right})")
        
        # 使用反射填充避免边界效应
        if is_color:
            temp = np.pad(image, 
                         ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)), 
                         mode='reflect')
        else:
            temp = np.pad(image, 
                         ((pad_top, pad_bottom), (pad_left, pad_right)), 
                         mode='reflect')
        
        # Arnold变换迭代
        for _ in range(iterations):
            new_temp = np.zeros_like(temp)
            for i in range(N):
                for j in range(N):
                    new_i = (i + j) % N
                    new_j = (i + 2 * j) % N
                    if is_color:
                        new_temp[new_i, new_j] = temp[i, j]
                    else:
                        new_temp[new_i, new_j] = temp[i, j]
            temp = new_temp

        # 返回填充后的正方形图像和填充信息
        padding_info = {
            'pad_top': pad_top,
            'pad_bottom': pad_bottom,
            'pad_left': pad_left,
            'pad_right': pad_right,
            'original_h': h,
            'original_w': w,
            'square_size': N
        }
        
        return temp, padding_info

    def decrypt(self, image, iterations=10):
        """Arnold解密 - 对正方形图像进行解密并裁剪回原始尺寸"""
        if image is None:
            raise ValueError("输入图像为None")
            
        # 如果没有在加密时设置original_shape，则尝试从图像本身获取
        if self.original_shape is None:
            self.original_shape = image.shape

        if len(image.shape) == 3:
            c = image.shape[2]
            if c == 4: # RGBA图像
                rgb_image = image[:, :, :3]
                alpha_channel = image[:, :, 3]
                decrypted_rgb = self._inverse_arnold_transform_square(rgb_image, iterations)
                decrypted_alpha = self._inverse_arnold_transform_square(alpha_channel, iterations)
                decrypted = np.dstack((decrypted_rgb, decrypted_alpha))
            else: # RGB/BGR图像
                decrypted = self._inverse_arnold_transform_square(image, iterations)
        else: # 灰度图像
            decrypted = self._inverse_arnold_transform_square(image, iterations)

        return decrypted.astype(np.uint8)

    def _inverse_arnold_transform_square(self, image, iterations):
        """逆Arnold变换 - 对正方形图像进行逆变换并裁剪回原始尺寸"""
        if len(image.shape) == 3:
            is_color = True
        else:
            is_color = False
        
        # 使用保存的填充信息
        if self.padding_info is None:
            # 如果没有填充信息，假设图像已经是正方形，且没有填充
            pad_top = 0
            pad_left = 0
            original_h, original_w = image.shape[:2]
            N = max(original_h, original_w) # 假设N就是当前图像的尺寸
            logger.warning("Arnold解密：没有找到填充信息，无法正确裁剪。将尝试使用当前图像尺寸。")
        else:
            pad_top = self.padding_info['pad_top']
            pad_left = self.padding_info['pad_left']
            original_h = self.padding_info['original_h']
            original_w = self.padding_info['original_w']
            N = self.padding_info['square_size']
            logger.debug(f"Arnold解密：使用填充信息裁剪: {N}x{N} -> {original_w}x{original_h}")
        
        # 逆Arnold变换迭代
        temp = image.copy()
        for _ in range(iterations):
            new_temp = np.zeros_like(temp)
            for i in range(N):  # 使用N作为迭代范围
                for j in range(N):  # 使用N作为迭代范围
                    # 逆Arnold变换公式
                    orig_i = (2 * i - j) % N
                    orig_j = (-i + j) % N
                    
                    # 处理负索引
                    if orig_i < 0:
                        orig_i += N
                    if orig_j < 0:
                        orig_j += N
                    
                    if is_color:
                        new_temp[orig_i, orig_j] = temp[i, j]
                    else:
                        new_temp[orig_i, orig_j] = temp[i, j]
            temp = new_temp

        # 裁剪回原始尺寸
        if self.padding_info is not None:
            if is_color:
                result = temp[pad_top : pad_top + original_h, pad_left : pad_left + original_w, :]
            else:
                result = temp[pad_top : pad_top + original_h, pad_left : pad_left + original_w]
            logger.debug(f"Arnold解密：成功裁剪: {temp.shape} -> {result.shape}")
        else:
            result = temp
            logger.warning("Arnold解密：无法裁剪，使用完整图像。")

        return result.astype(image.dtype)

    def get_padded_square(self, image):
        """获取填充后的正方形图像（不进行Arnold变换）"""
        if image is None:
            raise ValueError("输入图像为None")
            
        if len(image.shape) == 3:
            h, w, c = image.shape
            is_color = True
        else:
            h, w = image.shape
            is_color = False
        
        # 找到最接近的2的幂次方尺寸
        N = 1
        while N < max(h, w):
            N *= 2
        
        # 计算填充尺寸（居中填充）
        pad_top = (N - h) // 2
        pad_bottom = N - h - pad_top
        pad_left = (N - w) // 2
        pad_right = N - w - pad_left
        
        # 使用反射填充
        if is_color:
            padded = np.pad(image, 
                           ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)), 
                           mode='reflect')
        else:
            padded = np.pad(image, 
                           ((pad_top, pad_bottom), (pad_left, pad_right)), 
                           mode='reflect')
        
        return padded.astype(np.uint8)

    def get_state(self):
        """获取加密器状态，用于序列化"""
        return {
            'original_shape': self.original_shape,
            'padding_info': self.padding_info
        }
    
    def set_state(self, state):
        """设置加密器状态，用于反序列化"""
        if state:
            self.original_shape = state.get('original_shape')
            self.padding_info = state.get('padding_info')