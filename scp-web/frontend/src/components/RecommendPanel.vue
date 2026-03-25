<template>
  <el-card class="recommend-card">
    <template #header>
      <div class="card-header">
        <span>
          <el-icon style="vertical-align:-2px;margin-right:4px"><magic-stick /></el-icon>
          智能算法推荐
        </span>
        <el-tag v-if="modelExists" type="success" size="small">模型已就绪</el-tag>
        <el-tag v-else type="warning" size="small">模型未训练</el-tag>
      </div>
    </template>

    <!-- 模型未训练提示 -->
    <el-alert
      v-if="!modelExists"
      title="推荐模型尚未训练"
      description="请先在「数据大屏」页面点击「训练推荐模型」按钮，积累至少 10 条分析记录后即可训练。"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom:10px"
    />

    <!-- 无图像时提示 -->
    <el-alert
      v-else-if="!imageId"
      title="请先上传图像"
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom:10px"
    />

    <!-- 推荐操作区 -->
    <template v-else>
      <el-button
        type="primary"
        size="small"
        :loading="loading"
        style="width:100%;margin-bottom:12px"
        @click="getRecommendation"
      >
        {{ loading ? '分析中...' : '为当前图像推荐算法' }}
      </el-button>

      <!-- 推荐结果 -->
      <transition name="fade">
        <div v-if="recommendations.length > 0" class="result-area">

          <!-- 最优推荐 -->
          <div class="top-recommend">
            <el-icon color="#E6A23C" size="18"><trophy /></el-icon>
            <span class="top-label">推荐使用：</span>
            <span class="top-algo">{{ recommendations[0].algorithm }}</span>
            <el-tag type="success" size="small" style="margin-left:6px">
              置信度 {{ pct(recommendations[0].confidence) }}
            </el-tag>
          </div>

          <!-- 置信度条形列表 -->
          <div class="rank-list">
            <div
              v-for="item in recommendations"
              :key="item.algorithm"
              class="rank-item"
            >
              <span class="rank-algo" :class="{ 'rank-first': item.rank === 1 }">
                {{ item.rank }}. {{ item.algorithm }}
              </span>
              <el-progress
                :percentage="Math.round(item.confidence * 100)"
                :color="barColor(item.rank)"
                :stroke-width="10"
                style="flex:1;margin:0 10px"
              />
              <span class="rank-pct">{{ pct(item.confidence) }}</span>
            </div>
          </div>

          <!-- 图像特征展示 -->
          <el-collapse style="margin-top:10px">
            <el-collapse-item title="查看图像特征分析" name="features">
              <div class="feature-grid">
                <div v-for="(val, key) in features" :key="key" class="feature-item">
                  <div class="feature-key">{{ featureLabel(key) }}</div>
                  <div class="feature-val">{{ val }}</div>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>

          <!-- 一键应用按钮 -->
          <el-button
            type="success"
            size="small"
            style="width:100%;margin-top:10px"
            @click="applyRecommendation"
          >
            应用推荐算法：{{ recommendations[0].algorithm }}
          </el-button>

        </div>
      </transition>
    </template>
  </el-card>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { MagicStick, Trophy } from '@element-plus/icons-vue'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? ''

const FEATURE_LABELS = {
  mean_pixel:    '像素均值（归一化）',
  std_pixel:     '像素标准差（归一化）',
  entropy_orig:  '原始信息熵（归一化）',
  aspect_ratio:  '宽高比特征',
  channel:       '通道数特征',
  size:          '图像尺寸类别',
}

export default {
  name: 'RecommendPanel',
  components: { MagicStick, Trophy },

  props: {
    // 父组件传入已上传图像的 image_id
    imageId: { type: String, default: '' },
  },

  emits: ['apply'],  // 触发父组件切换算法选择

  data() {
    return {
      modelExists:     false,
      loading:         false,
      recommendations: [],   // [{algorithm, confidence, rank}]
      features:        {},   // {mean_pixel: 0.51, ...}
    }
  },

  watch: {
    // 每次 imageId 变化时清空旧结果
    imageId(newVal) {
      if (!newVal) {
        this.recommendations = []
        this.features = {}
      }
    },
  },

  mounted() {
    this.checkModelStatus()
  },

  methods: {
    async checkModelStatus() {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/recommend/status`)
        this.modelExists = res.data.model_exists ?? false
      } catch {
        this.modelExists = false
      }
    },

    async getRecommendation() {
      if (!this.imageId) return

      this.loading = true
      this.recommendations = []
      this.features = {}

      try {
        const res = await axios.post(`${BACKEND_URL}/api/recommend/predict`, {
          image_id: this.imageId,
        })
        const data = res.data

        if (!data.model_exists) {
          this.modelExists = false
          ElMessage.warning(data.message || '模型未训练')
          return
        }

        this.recommendations = data.recommendations ?? []
        this.features        = data.features        ?? {}

        if (this.recommendations.length > 0) {
          ElMessage.success(`推荐算法：${this.recommendations[0].algorithm}`)
        }
      } catch (error) {
        ElMessage.error('推荐失败: ' + (error.response?.data?.error || error.message))
      } finally {
        this.loading = false
      }
    },

    applyRecommendation() {
      if (this.recommendations.length === 0) return
      const best = this.recommendations[0].algorithm
      this.$emit('apply', best)
      ElMessage.success(`已切换到推荐算法：${best}`)
    },

    pct(val) {
      return (val * 100).toFixed(1) + '%'
    },

    barColor(rank) {
      if (rank === 1) return '#67C23A'
      if (rank === 2) return '#E6A23C'
      if (rank === 3) return '#409EFF'
      return '#C0C4CC'
    },

    featureLabel(key) {
      return FEATURE_LABELS[key] ?? key
    },
  },
}
</script>

<style scoped>
.recommend-card { margin-top: 16px; }
.card-header {
  font-weight: bold;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 最优推荐横幅 */
.top-recommend {
  display: flex;
  align-items: center;
  background: #fdf6ec;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
  gap: 4px;
}
.top-label { font-size: 13px; color: #606266; }
.top-algo  { font-size: 15px; font-weight: bold; color: #E6A23C; }

/* 排名列表 */
.rank-list   { display: flex; flex-direction: column; gap: 8px; }
.rank-item   { display: flex; align-items: center; }
.rank-algo   { font-size: 12px; color: #606266; min-width: 110px; white-space: nowrap; }
.rank-first  { color: #67C23A; font-weight: bold; }
.rank-pct    { font-size: 12px; color: #909399; min-width: 42px; text-align: right; }

/* 特征网格 */
.feature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 12px;
  font-size: 12px;
}
.feature-item { display: flex; justify-content: space-between; }
.feature-key  { color: #909399; }
.feature-val  { color: #303133; font-weight: 500; }

/* 动画 */
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }
</style>
