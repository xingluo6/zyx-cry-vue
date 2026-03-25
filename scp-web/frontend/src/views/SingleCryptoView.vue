<template>
  <el-row :gutter="20">
    <el-col :span="8">
      <el-card class="box-card">
        <template #header>
          <div class="card-header"><span>图像操作</span></div>
        </template>

        <el-upload class="upload-demo" drag :auto-upload="false"
          :show-file-list="false" :on-change="handleFileChange" accept="image/*">
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">拖拽文件到此 或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">支持 PNG, JPG, JPEG, BMP, TIFF</div>
          </template>
        </el-upload>

        <el-divider />

        <el-form label-width="100px" size="small">
          <el-form-item label="当前图像">
            <el-input v-model="originalImageName" readonly />
          </el-form-item>
        </el-form>

        <el-divider />

        <el-form label-width="100px" size="small">
          <el-form-item label="选择算法">
            <el-select v-model="selectedAlgorithm" placeholder="请选择加密算法">
              <el-option-group label="传统加密">
                <el-option v-for="a in classicAlgos" :key="a.value"
                  :label="a.label" :value="a.value" />
              </el-option-group>
              <el-option-group label="现代加密（推荐）">
                <el-option v-for="a in modernAlgos" :key="a.value"
                  :label="a.label" :value="a.value" />
              </el-option-group>
            </el-select>
          </el-form-item>
        </el-form>

        <el-card class="box-card" style="margin-top:10px">
          <template #header>
            <div class="card-header"><span>算法参数</span></div>
          </template>
          <AlgorithmParamsForm :algorithm="selectedAlgorithm" v-model="algorithmParams" />
        </el-card>

        <el-divider />

        <el-row :gutter="10" style="margin-bottom:10px">
          <el-col :span="12">
            <el-button type="primary" :loading="encryptLoading"
              :disabled="!originalImageId || !selectedAlgorithm"
              @click="encryptImage" style="width:100%">加密</el-button>
          </el-col>
          <el-col :span="12">
            <el-button type="success" :loading="decryptLoading"
              :disabled="!encryptedImageId"
              @click="decryptImage" style="width:100%">解密</el-button>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="24">
            <el-button type="info" :loading="analyzeLoading"
              :disabled="!originalImageId || !encryptedImageId"
              @click="analyzeImages" style="width:100%">运行统计分析</el-button>
          </el-col>
        </el-row>

        <div class="auto-analyze-row">
          <el-checkbox v-model="autoAnalyze" size="small">加密后自动运行统计分析</el-checkbox>
          <el-tooltip content="开启后加密完成即自动写入分析记录，数据大屏实时更新" placement="top">
            <el-icon color="#909399" style="cursor:help"><question-filled /></el-icon>
          </el-tooltip>
        </div>

        <el-divider content-position="left">
          <span style="font-size:11px;color:#909399">下载</span>
        </el-divider>
        <el-row :gutter="8">
          <el-col :span="12">
            <el-button size="small" :disabled="!encryptedImageId"
              @click="downloadImage(encryptedImageId,'加密图像')" style="width:100%">
              <el-icon><download /></el-icon>&nbsp;加密图像
            </el-button>
          </el-col>
          <el-col :span="12">
            <el-button size="small" :disabled="!decryptedImageId"
              @click="downloadImage(decryptedImageId,'解密图像')" style="width:100%">
              <el-icon><download /></el-icon>&nbsp;解密图像
            </el-button>
          </el-col>
        </el-row>
        <div v-if="encryptedImageId" class="download-hint">
          💡 下载加密图像后可重新上传，用相同参数解密以验证可逆性
        </div>

        <el-divider />
        <el-button @click="resetAll" size="small">重置所有</el-button>
      </el-card>

      <RecommendPanel :image-id="originalImageId" @apply="onApplyRecommendation" />

      <el-card class="box-card" style="margin-top:16px">
        <template #header>
          <div class="card-header"><span>分析报告</span></div>
        </template>
        <el-input type="textarea" :rows="15" v-model="analysisReport"
          placeholder="分析结果将显示在此处" readonly />
      </el-card>
    </el-col>

    <el-col :span="16">
      <el-row :gutter="20">
        <ImageDisplay title="原始图像" :base64Image="originalImageBase64"
          :shape="originalImageShape" :loading="uploadLoading" placeholderText="请上传图像" />
        <ImageDisplay title="加密图像" :base64Image="encryptedImageBase64"
          :shape="encryptedImageShape" :loading="encryptLoading" placeholderText="加密后显示" />
        <ImageDisplay title="解密图像" :base64Image="decryptedImageBase64"
          :shape="decryptedImageShape" :loading="decryptLoading" placeholderText="解密后显示" />
      </el-row>
      <AnalysisCharts :analysisResults="analysisResults" />
    </el-col>
  </el-row>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import ImageDisplay        from '@/components/ImageDisplay.vue'
import AlgorithmParamsForm from '@/components/AlgorithmParamsForm.vue'
import AnalysisCharts      from '@/components/AnalysisCharts.vue'
import RecommendPanel      from '@/components/RecommendPanel.vue'
import { UploadFilled, Download, QuestionFilled } from '@element-plus/icons-vue'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? ''

export default {
  name: 'SingleCryptoView',
  components: { ImageDisplay, AlgorithmParamsForm, AnalysisCharts, RecommendPanel,
                UploadFilled, Download, QuestionFilled },
  data() {
    return {
      originalImageId: null, originalImageBase64: '', originalImageShape: [],
      originalImageName: '未选择文件',

      // ✅ 分组显示
      classicAlgos: [
        { label: 'Arnold变换',       value: 'Arnold变换' },
        { label: 'XOR加密',          value: 'XOR加密' },
        { label: 'XXTEA加密',        value: 'XXTEA加密' },
        { label: 'AES加密',          value: 'AES加密' },
        { label: 'Logistic混沌加密', value: 'Logistic混沌加密' },
      ],
      modernAlgos: [
        { label: 'AES-GCM加密（认证加密）',  value: 'AES-GCM加密' },
        { label: 'ChaCha20加密（流密码）',    value: 'ChaCha20加密' },
        { label: 'RSA混合加密（非对称+对称）', value: 'RSA混合加密' },
      ],

      selectedAlgorithm: '', algorithmParams: {},
      encryptedImageId: null, encryptedImageBase64: '', encryptedImageShape: [],
      algorithmState: null,
      decryptedImageId: null, decryptedImageBase64: '', decryptedImageShape: [],
      analysisReport: '', analysisResults: null,
      autoAnalyze: true,
      uploadLoading: false, encryptLoading: false,
      decryptLoading: false, analyzeLoading: false,
    }
  },

  methods: {
    onApplyRecommendation(algo) { this.selectedAlgorithm = algo },

    downloadImage(imageId, label) {
      if (!imageId) return
      const a = document.createElement('a')
      a.href = `${BACKEND_URL}/api/download/${imageId}`
      a.target = '_blank'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      ElMessage.success(`开始下载${label}`)
    },

    async handleFileChange(file) {
      if (!file.raw) return
      this.resetAll()
      this.uploadLoading = true
      const fd = new FormData(); fd.append('file', file.raw)
      try {
        const res  = await axios.post(`${BACKEND_URL}/api/upload_image`, fd,
          { headers: { 'Content-Type': 'multipart/form-data' } })
        const data = res.data
        this.originalImageId    = data.image_id
        this.originalImageName  = data.filename
        this.originalImageShape = data.original_shape
        const reader = new FileReader()
        reader.onload = e => { this.originalImageBase64 = e.target.result.split(',')[1] }
        reader.readAsDataURL(file.raw)
        if (data.is_duplicate) {
          ElMessage({ message: '图像已存在于图像库，已自动复用', type: 'info', duration: 3000 })
        } else {
          ElMessage.success('图像上传成功！')
        }
      } catch (err) {
        ElMessage.error('上传失败: ' + (err.response?.data?.error || err.message))
        this.resetAll()
      } finally {
        this.uploadLoading = false
      }
    },

    async encryptImage() {
      if (!this.originalImageId) return ElMessage.warning('请先上传图像。')
      if (!this.selectedAlgorithm) return ElMessage.warning('请选择一个加密算法。')
      this.encryptLoading = true
      this.encryptedImageBase64 = ''; this.encryptedImageShape = []
      this.decryptedImageId = null; this.decryptedImageBase64 = ''; this.decryptedImageShape = []
      this.analysisReport = ''; this.analysisResults = null
      try {
        const res  = await axios.post(`${BACKEND_URL}/api/encrypt`, {
          image_id: this.originalImageId, algorithm: this.selectedAlgorithm,
          params: this.algorithmParams,
        })
        const data = res.data
        this.encryptedImageId     = data.encrypted_image_id
        this.encryptedImageBase64 = data.encrypted_image_base64
        this.encryptedImageShape  = data.encrypted_shape
        this.algorithmState       = data.algorithm_state
        ElMessage.success('图像加密成功！')
        if (this.autoAnalyze) await this._runAnalysis()
      } catch (err) {
        ElMessage.error('加密失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.encryptLoading = false
      }
    },

    async decryptImage() {
      if (!this.encryptedImageId) return ElMessage.warning('请先加密图像。')
      this.decryptLoading = true
      this.decryptedImageId = null; this.decryptedImageBase64 = ''; this.decryptedImageShape = []
      try {
        const res  = await axios.post(`${BACKEND_URL}/api/decrypt`, {
          encrypted_image_id: this.encryptedImageId,
          algorithm: this.selectedAlgorithm, params: this.algorithmParams,
          algorithm_state: this.algorithmState,
        })
        const data = res.data
        this.decryptedImageId    = data.decrypted_image_id
        this.decryptedImageBase64 = data.decrypted_image_base64
        this.decryptedImageShape  = data.decrypted_shape
        ElMessage.success('图像解密成功！')
      } catch (err) {
        ElMessage.error('解密失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.decryptLoading = false
      }
    },

    async analyzeImages() {
      if (!this.originalImageId || !this.encryptedImageId)
        return ElMessage.warning('请先上传原始图像并加密。')
      await this._runAnalysis()
    },

    async _runAnalysis() {
      this.analyzeLoading = true
      try {
        const res = await axios.post(`${BACKEND_URL}/api/analyze`, {
          original_image_id:  this.originalImageId,
          encrypted_image_id: this.encryptedImageId,
        })
        this.analysisReport  = res.data.formatted_report
        this.analysisResults = res.data.analysis_results
        ElMessage.success('统计分析完成，已写入数据大屏')
      } catch (err) {
        ElMessage.error('分析失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.analyzeLoading = false
      }
    },

    resetAll() {
      this.originalImageId = null; this.originalImageBase64 = ''
      this.originalImageShape = []; this.originalImageName = '未选择文件'
      this.selectedAlgorithm = ''; this.algorithmParams = {}
      this.encryptedImageId = null; this.encryptedImageBase64 = ''
      this.encryptedImageShape = []; this.algorithmState = null
      this.decryptedImageId = null; this.decryptedImageBase64 = ''
      this.decryptedImageShape = []
      this.analysisReport = ''; this.analysisResults = null
      ElMessage.info('所有状态已重置。')
    },
  },
}
</script>

<style scoped>
.box-card { margin-bottom: 16px; }
.card-header { font-weight: 600; }
.upload-demo { text-align: center; }
.el-select   { width: 100%; }
.auto-analyze-row {
  display: flex; align-items: center; gap: 6px;
  margin-top: 10px; padding: 6px 8px;
  background: #f0f7ff; border-radius: 6px; border: 1px solid #d0e8ff;
}
.download-hint {
  margin-top: 8px; font-size: 11px; color: #909399;
  line-height: 1.5; padding: 6px 8px;
  background: #f5f7fa; border-radius: 6px;
}
</style>
