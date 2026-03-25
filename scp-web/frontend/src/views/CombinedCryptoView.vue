<template>
  <el-row :gutter="20">
    <el-col :span="8">
      <el-card class="box-card">
        <template #header>
          <div class="card-header"><span>组合加密操作</span></div>
        </template>

        <el-upload class="upload-demo" drag :auto-upload="false"
          :show-file-list="false" :on-change="handleFileChange" accept="image/*">
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">拖拽文件到此 或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">支持 PNG, JPG, JPEG, BMP, TIFF 格式</div>
          </template>
        </el-upload>

        <el-divider />

        <el-form label-width="100px" size="small">
          <el-form-item label="当前图像">
            <el-input v-model="originalImageName" readonly />
          </el-form-item>
        </el-form>

        <el-divider />

        <!-- 算法链管理 -->
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>加密算法链</span>
              <el-button type="primary" link size="small" @click="addAlgorithmStep">
                + 添加步骤
              </el-button>
            </div>
          </template>
          <div v-if="algorithmChain.length === 0"
            style="text-align:center;color:#909399;font-size:13px;padding:8px 0">
            点击「添加步骤」构建加密链
          </div>
          <div v-for="(step, index) in algorithmChain" :key="index" style="margin-bottom:10px">
            <el-card shadow="hover">
              <template #header>
                <div class="card-header">
                  <span style="font-size:12px">步骤 {{ index + 1 }}</span>
                  <el-button type="danger" link size="small" @click="removeAlgorithmStep(index)">
                    删除
                  </el-button>
                </div>
              </template>
              <el-form label-width="60px" size="small">
                <el-form-item label="算法">
                  <el-select v-model="step.name" placeholder="选择算法" style="width:100%">
                    <el-option v-for="a in singleAlgorithms" :key="a.value"
                      :label="a.label" :value="a.value" :disabled="a.disabled" />
                  </el-select>
                </el-form-item>
              </el-form>
              <AlgorithmParamsForm v-if="step.name" :algorithm="step.name" v-model="step.params" />
            </el-card>
          </div>
        </el-card>

        <el-divider />

        <el-row :gutter="10" style="margin-bottom:10px">
          <el-col :span="12">
            <el-button type="primary" :loading="encryptLoading"
              :disabled="!originalImageId || algorithmChain.length === 0"
              @click="combinedEncrypt" style="width:100%">组合加密</el-button>
          </el-col>
          <el-col :span="12">
            <el-button type="success" :loading="decryptLoading"
              :disabled="!encryptedImageId"
              @click="combinedDecrypt" style="width:100%">组合解密</el-button>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="24">
            <el-button type="info" :loading="analyzeLoading"
              :disabled="!originalImageId || !encryptedImageId"
              @click="combinedAnalyze" style="width:100%">运行统计分析</el-button>
          </el-col>
        </el-row>

        <!-- 🆕 下载按钮 -->
        <el-divider content-position="left" style="font-size:12px;color:#909399">
          下载文件
        </el-divider>
        <el-row :gutter="8">
          <el-col :span="12">
            <el-button size="small" :disabled="!encryptedImageId"
              @click="downloadImage(encryptedImageId, '加密图像')" style="width:100%">
              <el-icon><download /></el-icon>&nbsp;加密图像
            </el-button>
          </el-col>
          <el-col :span="12">
            <el-button size="small" :disabled="!decryptedImageId"
              @click="downloadImage(decryptedImageId, '解密图像')" style="width:100%">
              <el-icon><download /></el-icon>&nbsp;解密图像
            </el-button>
          </el-col>
        </el-row>
        <div v-if="encryptedImageId" class="download-hint">
          💡 下载加密图像后可重新上传，用相同算法链解密以验证可逆性
        </div>

        <el-divider />
        <el-button @click="resetAll">重置所有</el-button>
      </el-card>

      <!-- 分析报告 -->
      <el-card class="box-card" style="margin-top:16px">
        <template #header>
          <div class="card-header"><span>分析报告</span></div>
        </template>
        <el-input type="textarea" :rows="15" v-model="analysisReport"
          placeholder="分析结果将显示在此处" readonly />
      </el-card>
    </el-col>

    <!-- 右侧图像显示 -->
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
import { UploadFilled, Download } from '@element-plus/icons-vue'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? ''

export default {
  name: 'CombinedCryptoView',
  components: { ImageDisplay, AlgorithmParamsForm, AnalysisCharts, UploadFilled, Download },

  data() {
    return {
      originalImageId: null, originalImageBase64: '', originalImageShape: [],
      originalImageName: '未选择文件',
      singleAlgorithms: [
        { label: 'Arnold变换',       value: 'Arnold' },
        { label: 'XOR加密',          value: 'XOR' },
        { label: 'XXTEA加密',        value: 'XXTEA' },
        { label: 'AES加密',          value: 'AES' },
        { label: 'Logistic混沌加密', value: 'Logistic' },
      ],
      algorithmChain: [],
      encryptedImageId: null, encryptedImageBase64: '', encryptedImageShape: [],
      combinedEncryptorState: null,
      decryptedImageId: null, decryptedImageBase64: '', decryptedImageShape: [],
      analysisReport: '', analysisResults: null,
      uploadLoading: false, encryptLoading: false,
      decryptLoading: false, analyzeLoading: false,
    }
  },

  methods: {
    downloadImage(imageId, label) {
      if (!imageId) return
      const a = document.createElement('a')
      a.href   = `${BACKEND_URL}/api/download/${imageId}`
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

    async combinedEncrypt() {
      if (!this.originalImageId) return ElMessage.warning('请先上传图像。')
      if (this.algorithmChain.length === 0) return ElMessage.warning('请至少添加一个加密步骤。')
      this.encryptLoading = true
      this.encryptedImageBase64 = ''; this.encryptedImageShape = []
      this.decryptedImageId = null; this.decryptedImageBase64 = ''; this.decryptedImageShape = []
      this.analysisReport = ''; this.analysisResults = null
      try {
        const res  = await axios.post(`${BACKEND_URL}/api/combined_encrypt`, {
          image_id: this.originalImageId, algorithms: this.algorithmChain,
        })
        const data = res.data
        this.encryptedImageId       = data.encrypted_image_id
        this.encryptedImageBase64   = data.encrypted_image_base64
        this.encryptedImageShape    = data.encrypted_shape
        this.combinedEncryptorState = data.combined_encryptor_state
        ElMessage.success('组合加密成功！')
      } catch (err) {
        ElMessage.error('组合加密失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.encryptLoading = false
      }
    },

    async combinedDecrypt() {
      if (!this.encryptedImageId) return ElMessage.warning('请先进行组合加密。')
      if (!this.combinedEncryptorState) return ElMessage.warning('未能获取加密状态，请重新加密。')
      this.decryptLoading = true
      this.decryptedImageId = null; this.decryptedImageBase64 = ''; this.decryptedImageShape = []
      this.analysisReport = ''; this.analysisResults = null
      try {
        const res  = await axios.post(`${BACKEND_URL}/api/combined_decrypt`, {
          encrypted_image_id: this.encryptedImageId,
          combined_encryptor_state: this.combinedEncryptorState,
        })
        const data = res.data
        this.decryptedImageId    = data.decrypted_image_id    // ✅ 供下载
        this.decryptedImageBase64 = data.decrypted_image_base64
        this.decryptedImageShape  = data.decrypted_shape
        ElMessage.success('组合解密成功！')
      } catch (err) {
        ElMessage.error('组合解密失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.decryptLoading = false
      }
    },

    async combinedAnalyze() {
      if (!this.originalImageId || !this.encryptedImageId)
        return ElMessage.warning('请先上传原始图像并执行组合加密。')
      this.analyzeLoading = true
      this.analysisReport = ''; this.analysisResults = null
      try {
        const res = await axios.post(`${BACKEND_URL}/api/combined_analyze`, {
          original_image_id: this.originalImageId,
          encrypted_image_id: this.encryptedImageId,
        })
        this.analysisReport  = res.data.formatted_report
        this.analysisResults = res.data.analysis_results
        ElMessage.success('统计分析完成！')
      } catch (err) {
        ElMessage.error('分析失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.analyzeLoading = false
      }
    },

    addAlgorithmStep()         { this.algorithmChain.push({ name: '', params: {} }) },
    removeAlgorithmStep(index) { this.algorithmChain.splice(index, 1) },

    resetAll() {
      this.originalImageId = null; this.originalImageBase64 = ''
      this.originalImageShape = []; this.originalImageName = '未选择文件'
      this.algorithmChain = []
      this.encryptedImageId = null; this.encryptedImageBase64 = ''
      this.encryptedImageShape = []; this.combinedEncryptorState = null
      this.decryptedImageId = null; this.decryptedImageBase64 = ''
      this.decryptedImageShape = []
      this.analysisReport = ''; this.analysisResults = null
      ElMessage.info('所有状态已重置。')
    },
  },
}
</script>

<style scoped>
.box-card    { margin-bottom: 16px; }
.card-header { font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
.upload-demo { text-align: center; }
.el-select   { width: 100%; }
.download-hint {
  margin-top: 8px; font-size: 11px; color: #909399;
  line-height: 1.5; padding: 6px 8px;
  background: #f5f7fa; border-radius: 6px;
}
</style>