<template>
  <el-card class="box-card">
    <template #header>
      <div class="card-header">
        <span>批量上传图像</span>
        <el-tag type="info" size="small" v-if="fileList.length > 0">
          已选 {{ fileList.length }} 张
        </el-tag>
      </div>
    </template>

    <el-upload class="upload-area" drag multiple :auto-upload="false"
      :show-file-list="false" :on-change="handleFileAdd" accept="image/*">
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">拖拽多张图片到此 或 <em>点击选择</em></div>
      <template #tip>
        <div class="el-upload__tip">支持 PNG / JPG / JPEG / BMP / TIFF，单次最多 20 张</div>
      </template>
    </el-upload>

    <!-- 待上传列表 -->
    <div v-if="fileList.length > 0" class="file-list">
      <el-divider content-position="left" style="font-size:12px">待上传</el-divider>
      <div v-for="(f, idx) in fileList" :key="idx" class="file-item">
        <el-icon color="#909399"><document /></el-icon>
        <span class="file-name">{{ f.name }}</span>
        <span class="file-size">{{ fmt(f.size) }}</span>
        <el-button type="danger" link size="small" @click="fileList.splice(idx,1)">
          ×
        </el-button>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="actions">
      <el-button type="primary" :loading="uploading"
        :disabled="fileList.length === 0" @click="doUpload" style="flex:1">
        {{ uploading ? '上传中...' : `上传 ${fileList.length} 张` }}
      </el-button>
      <el-button :disabled="fileList.length === 0 || uploading"
        @click="fileList = []">清空</el-button>
    </div>

    <el-progress v-if="uploading" :percentage="progress"
      style="margin-top:10px" :stroke-width="6" />
  </el-card>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document } from '@element-plus/icons-vue'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? ''

export default {
  name: 'BatchUploader',
  components: { UploadFilled, Document },
  emits: ['uploaded'],

  data() {
    return { fileList: [], uploading: false, progress: 0 }
  },

  methods: {
    handleFileAdd(file) {
      if (this.fileList.length >= 20) { ElMessage.warning('单次最多 20 张'); return }
      const raw = file.raw
      if (!raw) return
      if (this.fileList.find(f => f.name === raw.name && f.size === raw.size)) return
      this.fileList.push(raw)
    },

    async doUpload() {
      if (!this.fileList.length) return
      this.uploading = true; this.progress = 0
      const fd = new FormData()
      this.fileList.forEach(f => fd.append('files', f))
      try {
        const res = await axios.post(`${BACKEND_URL}/api/batch_upload`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: e => {
            if (e.total) this.progress = Math.round(e.loaded / e.total * 100)
          },
        })
        const { count, new_count, dup_count, errors } = res.data

        if (count > 0) {
          // ✅ 展示去重统计
          if (dup_count > 0) {
            ElMessage({
              message: `上传完成：${new_count} 张新图像入库，${dup_count} 张已存在（自动跳过）`,
              type: 'success',
              duration: 4000,
            })
          } else {
            ElMessage.success(`成功上传 ${count} 张图像`)
          }
          this.$emit('uploaded', res.data.uploaded)
          this.fileList = []
        } else {
          ElMessage.error('没有图像上传成功')
        }
        errors?.forEach(e => ElMessage.warning(e))
      } catch (err) {
        ElMessage.error('上传失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.uploading = false; this.progress = 0
      }
    },

    fmt(b) {
      if (b < 1024)        return b + ' B'
      if (b < 1024 * 1024) return (b/1024).toFixed(1) + ' KB'
      return (b/1024/1024).toFixed(1) + ' MB'
    },
  },
}
</script>

<style scoped>
.card-header { font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
.upload-area { width: 100%; }
.file-list   { max-height: 200px; overflow-y: auto; margin-top: 8px; }
.file-item   {
  display: flex; align-items: center; gap: 6px;
  padding: 3px 0; font-size: 12px;
  border-bottom: 1px solid #f5f5f5;
}
.file-name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#303133; }
.file-size { color:#909399; min-width:50px; text-align:right; }
.actions   { margin-top:12px; display:flex; gap:8px; }
</style>