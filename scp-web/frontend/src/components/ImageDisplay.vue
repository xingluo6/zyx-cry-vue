<template>
  <el-card class="image-card" shadow="hover">
    <template #header>
      <div class="img-header">
        <span class="img-title">{{ title }}</span>
        <el-tag v-if="shape && shape.length > 0" type="info" size="small" round>
          {{ shape[1] }}×{{ shape[0] }}
          <span v-if="shape.length === 3"> · {{ shape[2] }}ch</span>
        </el-tag>
      </div>
    </template>

    <div class="image-container" v-loading="loading" element-loading-text="处理中...">
      <!-- 有图像时展示 -->
      <transition name="img-fade" mode="out-in">
        <div v-if="imageUrl" class="img-wrapper" :key="imageUrl">
          <img :src="imageUrl" alt="Image" class="responsive-image" />
        </div>
        <!-- 占位状态 -->
        <div v-else class="placeholder">
          <el-icon size="32" color="#c0c4cc"><picture /></el-icon>
          <span class="placeholder-text">{{ placeholderText }}</span>
        </div>
      </transition>
    </div>
  </el-card>
</template>

<script>
import { Picture } from '@element-plus/icons-vue'

export default {
  name: 'ImageDisplay',
  components: { Picture },
  props: {
    title:           { type: String,  default: '图像' },
    base64Image:     { type: String,  default: '' },
    shape:           { type: Array,   default: () => [] },
    loading:         { type: Boolean, default: false },
    placeholderText: { type: String,  default: '无图像' },
  },
  computed: {
    imageUrl() {
      return this.base64Image
        ? `data:image/png;base64,${this.base64Image}`
        : ''
    },
  },
}
</script>

<style scoped>
.image-card {
  width: 32%;
  margin: 0 0.5%;
  display: inline-block;
  vertical-align: top;
}

/* 头部：标题 + 尺寸标签 */
.img-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.img-title {
  font-weight: 600;
  font-size: 13px;
  color: #1a1f36;
}

/* 图像容器 */
.image-container {
  height: 220px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #f5f7fa 0%, #eef0f5 100%);
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}

.img-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.responsive-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

/* 占位 */
.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.placeholder-text {
  font-size: 12px;
  color: #c0c4cc;
  letter-spacing: 0.5px;
}

/* 过渡动画 */
.img-fade-enter-active { transition: opacity 0.3s ease; }
.img-fade-leave-active { transition: opacity 0.15s ease; }
.img-fade-enter-from, .img-fade-leave-to { opacity: 0; }
</style>