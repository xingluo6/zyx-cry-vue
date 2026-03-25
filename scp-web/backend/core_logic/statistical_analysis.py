# backend/core_logic/statistical_analysis.py
import numpy as np
import cv2
from scipy.stats import entropy
import logging

logger = logging.getLogger(__name__)

class StatisticalAnalysis:
    """统计分析类"""
    @staticmethod
    def calculate_histogram(image):
        """
        计算图像的直方图。
        对于彩色图像，返回BGR三个通道的直方图。
        对于灰度图像，返回灰度通道的直方图。
        直方图数据被扁平化为列表，方便JSON序列化和前端ECharts处理。
        """
        if len(image.shape) == 3:
            # 对于彩色图像，计算BGR三个通道的直方图
            # cv2.calcHist 返回的数组形状是 (256, 1)，需要flatten().tolist()
            hist_b = cv2.calcHist([image], [0], None, [256], [0, 256]).flatten().tolist()
            hist_g = cv2.calcHist([image], [1], None, [256], [0, 256]).flatten().tolist()
            hist_r = cv2.calcHist([image], [2], None, [256], [0, 256]).flatten().tolist()
            return {'b': hist_b, 'g': hist_g, 'r': hist_r}
        else:
            # 对于灰度图像，计算单个通道的直方图
            hist = cv2.calcHist([image], [0], None, [256], [0, 256]).flatten().tolist()
            return {'gray': hist}

    @staticmethod
    def calculate_correlation(image, direction='horizontal'):
        """
        计算像素相关性。
        支持 'horizontal', 'vertical', 'diagonal', 'anti_diagonal' 四个方向。
        彩色图像会先转换为灰度图进行计算。
        """
        if len(image.shape) == 3:
            # 转换为灰度图计算相关性
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        h, w = image.shape

        if direction == 'horizontal':
            x = image[:, :-1].flatten()
            y = image[:, 1:].flatten()
        elif direction == 'vertical':
            x = image[:-1, :].flatten()
            y = image[1:, :].flatten()
        elif direction == 'diagonal': # 主对角线
            x = image[:-1, :-1].flatten()
            y = image[1:, 1:].flatten()
        elif direction == 'anti_diagonal': # 副对角线
            x = image[:-1, 1:].flatten()
            y = image[1:, :-1].flatten()
        else:
            raise ValueError("Invalid direction. Choose 'horizontal', 'vertical', 'diagonal', or 'anti_diagonal'.")

        if len(x) == 0 or len(y) == 0:
            return 0.0 # 避免空数组导致错误
            
        correlation = np.corrcoef(x, y)[0, 1]
        return correlation if not np.isnan(correlation) else 0.0

    @staticmethod
    def calculate_entropy(image):
        """
        计算图像的信息熵。
        彩色图像会先转换为灰度图进行计算。
        """
        if len(image.shape) == 3:
            # 转换为灰度图计算信息熵
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        hist = cv2.calcHist([image], [0], None, [256], [0, 256])
        hist_prob = hist / hist.sum()
        hist_prob = hist_prob.flatten()
        hist_prob = hist_prob[hist_prob > 0] # 过滤掉概率为0的bin

        img_entropy = entropy(hist_prob, base=2)
        return img_entropy

    @staticmethod
    def calculate_chi_square_uniformity(image):
        """
        计算直方图均匀性的卡方检验值。
        彩色图像会先转换为灰度图进行计算。
        值越小表示直方图越接近均匀分布。
        """
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        hist = cv2.calcHist([image], [0], None, [256], [0, 256]).flatten()
        
        # 期望频率：如果图像是均匀的，每个灰度级的像素数量应该大致相等
        expected_freq = np.full(256, image.size / 256.0)
        
        # 避免除以0，并确保所有bin都参与计算
        # 加上一个很小的epsilon值避免除以零
        chi2_stat = np.sum((hist - expected_freq)**2 / (expected_freq + 1e-9))
        
        return chi2_stat

    @staticmethod
    def calculate_moments(image):
        """
        计算像素均值、方差和标准差。
        彩色图像会先转换为灰度图进行计算。
        """
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
        mean = np.mean(image)
        variance = np.var(image)
        std_dev = np.std(image)
        return mean, variance, std_dev

    @staticmethod
    def calculate_average_run_length(image):
        """
        计算图像的平均运行长度 (ARL)。
        彩色图像会先转换为灰度图进行计算。
        ARL值越小表示图像的随机性越高。
        """
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        total_run_lengths = 0
        total_runs = 0
        
        # 水平方向
        for row in image:
            if len(row) == 0: continue # 避免空行
            current_pixel = row[0]
            current_run_length = 1
            for i in range(1, len(row)):
                if row[i] == current_pixel:
                    current_run_length += 1
                else:
                    total_run_lengths += current_run_length
                    total_runs += 1
                    current_pixel = row[i]
                    current_run_length = 1
            total_run_lengths += current_run_length # 添加最后一个运行
            total_runs += 1
            
        # 垂直方向
        for col_idx in range(image.shape[1]):
            if image.shape[0] == 0: continue # 避免空列
            current_pixel = image[0, col_idx]
            current_run_length = 1
            for i in range(1, image.shape[0]):
                if image[i, col_idx] == current_pixel:
                    current_run_length += 1
                else:
                    total_run_lengths += current_run_length
                    total_runs += 1
                    current_pixel = image[i, col_idx]
                    current_run_length = 1
            total_run_lengths += current_run_length # 添加最后一个运行
            total_runs += 1

        if total_runs == 0:
            return 0.0
        return total_run_lengths / total_runs

    @staticmethod
    def calculate_difference_image(original, encrypted):
        """
        计算原始图像和加密图像的绝对差值图像。
        返回一个灰度图像，表示像素差异的绝对值。
        """
        # 确保尺寸一致
        if original.shape != encrypted.shape:
            min_h = min(original.shape[0], encrypted.shape[0])
            min_w = min(original.shape[1], encrypted.shape[1])
            original = original[:min_h, :min_w]
            encrypted = encrypted[:min_h, :min_w]

        # 如果是彩色图像，转换为灰度图进行差值计算
        if len(original.shape) == 3:
            diff_image = cv2.absdiff(cv2.cvtColor(original, cv2.COLOR_BGR2GRAY), 
                                     cv2.cvtColor(encrypted, cv2.COLOR_BGR2GRAY))
        else:
            diff_image = cv2.absdiff(original, encrypted)
        
        return diff_image

    @staticmethod
    def npcr_uaci(original, encrypted):
        """
        计算NPCR (像素变化率) 和 UACI (统一平均变化强度)。
        这两个指标用于评估加密算法对明文变化的敏感度。
        彩色图像会先转换为灰度图进行计算。
        """
        # 确保图像为灰度图进行比较
        if len(original.shape) == 3:
            original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
        else:
            original_gray = original
            
        if len(encrypted.shape) == 3:
            encrypted_gray = cv2.cvtColor(encrypted, cv2.COLOR_BGR2GRAY)
        else:
            encrypted_gray = encrypted

        # 确保尺寸一致
        if original_gray.shape != encrypted_gray.shape:
            min_h = min(original_gray.shape[0], encrypted_gray.shape[0])
            min_w = min(original_gray.shape[1], encrypted_gray.shape[1])
            original_gray = original_gray[:min_h, :min_w]
            encrypted_gray = encrypted_gray[:min_h, :min_w]

        # NPCR (Number of Pixels Change Rate)
        # 统计加密前后灰度值不同的像素点数量
        diff_pixels = (original_gray.astype(np.int16) != encrypted_gray.astype(np.int16))
        npcr = np.sum(diff_pixels) / original_gray.size * 100

        # UACI (Unified Average Changing Intensity)
        # 衡量加密前后像素值变化的平均强度
        uaci = np.mean(np.abs(original_gray.astype(float) - encrypted_gray.astype(float))) / 255 * 100

        return npcr, uaci

    @staticmethod
    def calculate_psnr(original, encrypted):
        """
        计算PSNR (峰值信噪比)。
        用于衡量加密前后图像的失真程度。值越低通常表示加密效果越好。
        """
        # 确保尺寸一致
        if original.shape != encrypted.shape:
            min_h = min(original.shape[0], encrypted.shape[0])
            min_w = min(original.shape[1], encrypted.shape[1])
            original = original[:min_h, :min_w]
            encrypted = encrypted[:min_h, :min_w]

        mse = np.mean((original.astype(float) - encrypted.astype(float)) ** 2)
        if mse == 0:
            return float('inf') # 完美匹配，PSNR为无穷大
        psnr = 20 * np.log10(255.0 / np.sqrt(mse))
        return psnr

    @staticmethod
    def analyze_security(original, encrypted):
        """
        综合安全性分析，计算多项指标并给出综合评分。
        """
        analyzer = StatisticalAnalysis()
        
        # 计算各项指标
        entropy_orig = analyzer.calculate_entropy(original)
        entropy_enc = analyzer.calculate_entropy(encrypted)
        
        corr_h_orig = analyzer.calculate_correlation(original, 'horizontal')
        corr_h_enc = analyzer.calculate_correlation(encrypted, 'horizontal')
        
        corr_v_orig = analyzer.calculate_correlation(original, 'vertical')
        corr_v_enc = analyzer.calculate_correlation(encrypted, 'vertical')
        
        corr_d_orig = analyzer.calculate_correlation(original, 'diagonal')
        corr_d_enc = analyzer.calculate_correlation(encrypted, 'diagonal')
        
        chi2_orig = analyzer.calculate_chi_square_uniformity(original)
        chi2_enc = analyzer.calculate_chi_square_uniformity(encrypted)
        
        mean_orig, var_orig, std_dev_orig = analyzer.calculate_moments(original) # <--- 修正：变量名
        mean_enc, var_enc, std_dev_enc = analyzer.calculate_moments(encrypted)   # <--- 修正：变量名

        arl_orig = analyzer.calculate_average_run_length(original)
        arl_enc = analyzer.calculate_average_run_length(encrypted)
        
        npcr_val, uaci_val = analyzer.npcr_uaci(original, encrypted)
        psnr_val = analyzer.calculate_psnr(original, encrypted)

        # 新增：计算直方图数据
        histogram_original = analyzer.calculate_histogram(original)
        histogram_encrypted = analyzer.calculate_histogram(encrypted)
        
        # --- 综合安全性评分标准 ---
        security_score = 0
        
        # 信息熵评分 (权重20%)
        if entropy_enc > 7.9: security_score += 20
        elif entropy_enc > 7.5: security_score += 15
        elif entropy_enc > 7.0: security_score += 10
        elif entropy_enc > 6.5: security_score += 5
        
        # 相关性评分 (权重25%)
        corr_score = 0
        if abs(corr_h_enc) < 0.01: corr_score += 8
        elif abs(corr_h_enc) < 0.05: corr_score += 6
        elif abs(corr_h_enc) < 0.1: corr_score += 4
        
        if abs(corr_v_enc) < 0.01: corr_score += 8
        elif abs(corr_v_enc) < 0.05: corr_score += 6
        elif abs(corr_v_enc) < 0.1: corr_score += 4
        
        if abs(corr_d_enc) < 0.01: corr_score += 9
        elif abs(corr_d_enc) < 0.05: corr_score += 7
        elif abs(corr_d_enc) < 0.1: corr_score += 5
        
        security_score += min(corr_score, 25)

        # 直方图均匀性评分 (权重15%)
        if chi2_enc < 1000: security_score += 15
        elif chi2_enc < 5000: security_score += 10
        elif chi2_enc < 10000: security_score += 5

        # 像素统计矩评分 (权重15%)
        moment_score = 0
        if abs(mean_enc - 127.5) < 10: moment_score += 5
        if var_enc > 2000: moment_score += 5
        if std_dev_enc > 40: moment_score += 5 # <--- 修正：使用 std_dev_enc
        security_score += moment_score

        # 平均运行长度评分 (权重10%)
        if arl_enc < 2.0: security_score += 10
        elif arl_enc < 3.0: security_score += 7
        elif arl_enc < 4.0: security_score += 4
        
        # NPCR评分 (权重10%)
        if npcr_val > 99.6: security_score += 10
        elif npcr_val > 99.5: security_score += 8
        elif npcr_val > 99.0: security_score += 5

        # UACI评分 (权重5%)
        if abs(uaci_val - 33.46) < 1.0: security_score += 5
        elif abs(uaci_val - 33.46) < 2.0: security_score += 3
        
        return {
            'entropy_original': entropy_orig,
            'entropy_encrypted': entropy_enc,
            'correlation_h_original': corr_h_orig,
            'correlation_h_encrypted': corr_h_enc,
            'correlation_v_original': corr_v_orig,
            'correlation_v_encrypted': corr_v_enc,
            'correlation_d_original': corr_d_orig,
            'correlation_d_encrypted': corr_d_enc,
            'chi2_original': chi2_orig,
            'chi2_encrypted': chi2_enc,
            'mean_original': mean_orig,
            'mean_encrypted': mean_enc,
            'variance_original': var_orig,
            'variance_encrypted': var_enc,
            'std_dev_original': std_dev_orig, # <--- 修正：使用 std_dev_orig
            'std_dev_encrypted': std_dev_enc, # <--- 修正：使用 std_dev_enc
            'arl_original': arl_orig,
            'arl_encrypted': arl_enc,
            'npcr': npcr_val,
            'uaci': uaci_val,
            'psnr': psnr_val,
            'security_score': security_score,
            'histogram_original': histogram_original,
            'histogram_encrypted': histogram_encrypted
        }