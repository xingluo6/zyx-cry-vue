<template>
  <div class="library-page">

    <!-- 工具栏 -->
    <div class="lib-toolbar">
      <div class="toolbar-left">
        <el-upload multiple :auto-upload="false" :show-file-list="false"
          :on-change="handleUploadChange" accept="image/*">
          <el-button type="primary" size="small">
            <el-icon><upload-filled /></el-icon>&nbsp;上传图像
          </el-button>
        </el-upload>

        <el-divider direction="vertical" />

        <el-checkbox
          v-model="isAllSelected" :indeterminate="isIndeterminate"
          :disabled="images.length === 0" @change="toggleSelectAll"
          style="font-size:13px"
        >
          全选当前页
        </el-checkbox>

        <span class="select-count" v-if="selectedIds.length > 0">
          已选 {{ selectedIds.length }} 张
        </span>
      </div>

      <div class="toolbar-right">
        <el-button size="small" type="success"
          :disabled="selectedIds.length === 0" @click="sendToBatch">
          <el-icon><right /></el-icon>&nbsp;发送到批量处理
        </el-button>
        <el-button size="small" type="danger" plain
          :disabled="selectedIds.length === 0" @click="confirmDelete">
          <el-icon><delete /></el-icon>&nbsp;删除选中
        </el-button>
        <el-button size="small" type="warning" plain @click="confirmClean">
          <el-icon><brush /></el-icon>&nbsp;清理中间产物
        </el-button>
        <el-divider direction="vertical" />
        <span class="lib-total">共 <b>{{ total }}</b> 张</span>
      </div>
    </div>

    <!-- 上传进度 -->
    <el-progress v-if="uploading" :percentage="uploadProgress"
      :stroke-width="6" style="margin:8px 0" />

    <!-- 图像网格 -->
    <div v-loading="loading" class="grid-container"
      element-loading-text="加载中..." element-loading-background="rgba(240,242,247,0.8)">

      <div v-if="!loading && images.length === 0" class="empty-state">
        <el-empty description="图像库为空，请上传图像" :image-size="100" />
      </div>

      <div v-else class="image-grid">
        <div v-for="img in images" :key="img.image_id"
          class="grid-item" :class="{ selected: selectedIds.includes(img.image_id) }"
          @click="toggleSelect(img.image_id)">

          <!-- 选中标记 -->
          <div class="item-check">
            <el-icon v-if="selectedIds.includes(img.image_id)"
              color="#4f6ef7" size="16"><circle-check-filled /></el-icon>
            <div v-else class="check-ring"></div>
          </div>

          <!-- 缩略图 -->
          <div class="thumb-area">
            <img v-if="thumbnails[img.image_id]"
              :src="`data:image/png;base64,${thumbnails[img.image_id]}`"
              class="thumb-img" :alt="img.filename" />
            <div v-else class="thumb-loading">
              <el-icon size="24" color="#c0c4cc"><picture /></el-icon>
            </div>
          </div>

          <!-- 文件信息 -->
          <div class="item-info">
            <div class="item-name" :title="img.filename">{{ img.filename }}</div>
            <div class="item-meta">
              <span v-if="img.shape && img.shape.length >= 2">
                {{ img.shape[1] }}×{{ img.shape[0] }}
              </span>
              <span>{{ img.created_at.slice(5,16) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="pagination-bar" v-if="total > 0">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[12, 24, 48, 96]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @size-change="onSizeChange"
        @current-change="loadImages"
      />
    </div>

  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UploadFilled, Right, Delete, Brush, Picture, CircleCheckFilled,
} from '@element-plus/icons-vue'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? ''

export default {
  name: 'ImageLibraryView',
  components: { UploadFilled, Right, Delete, Brush, Picture, CircleCheckFilled },

  activated() { this.loadImages() },

  data() {
    return {
      images:      [],
      thumbnails:  {},
      total:       0,
      currentPage: 1,
      pageSize:    24,
      selectedIds: [],
      loading:     false,
      uploading:   false,
      uploadProgress: 0,
      _pendingFiles:  null,
    }
  },

  computed: {
    isAllSelected() {
      return this.images.length > 0 &&
        this.images.every(i => this.selectedIds.includes(i.image_id))
    },
    isIndeterminate() {
      return this.selectedIds.length > 0 && !this.isAllSelected
    },
  },

  mounted() { this.loadImages() },

  methods: {
    async loadImages() {
      this.loading = true
      try {
        const res = await axios.get(`${BACKEND_URL}/api/image_library`, {
          params: { page: this.currentPage, page_size: this.pageSize }
        })
        this.images = res.data.items ?? []
        this.total  = res.data.total  ?? 0
        // 清理旧缩略图缓存
        const cur = new Set(this.images.map(i => i.image_id))
        Object.keys(this.thumbnails).forEach(id => {
          if (!cur.has(id)) delete this.thumbnails[id]
        })
        this.loadThumbnails()
      } catch (err) {
        ElMessage.error('加载失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.loading = false
      }
    },

    onSizeChange(size) {
      this.pageSize    = size
      this.currentPage = 1
      this.loadImages()
    },

    async loadThumbnails() {
      const ids = this.images
        .filter(img => !this.thumbnails[img.image_id])
        .map(img => img.image_id)
      // 每批 4 个并发
      for (let i = 0; i < ids.length; i += 4) {
        await Promise.all(
          ids.slice(i, i + 4).map(id => this.loadThumb(id))
        )
      }
    },

    async loadThumb(id) {
      try {
        const res = await axios.get(
          `${BACKEND_URL}/api/image_library/thumbnail/${id}`
        )
        // Vue 响应式需要用 $set 或重新赋值整个对象
        this.thumbnails = { ...this.thumbnails, [id]: res.data.base64 }
      } catch {
        this.thumbnails = { ...this.thumbnails, [id]: null }
      }
    },

    toggleSelect(id) {
      const idx = this.selectedIds.indexOf(id)
      if (idx === -1) this.selectedIds.push(id)
      else             this.selectedIds.splice(idx, 1)
    },

    toggleSelectAll(val) {
      const curIds = this.images.map(i => i.image_id)
      if (val) {
        curIds.forEach(id => {
          if (!this.selectedIds.includes(id)) this.selectedIds.push(id)
        })
      } else {
        const curSet = new Set(curIds)
        this.selectedIds = this.selectedIds.filter(id => !curSet.has(id))
      }
    },

    handleUploadChange(file) {
      if (!this._pendingFiles) {
        this._pendingFiles = []
        setTimeout(() => this._flushUpload(), 150)
      }
      this._pendingFiles.push(file.raw)
    },

    async _flushUpload() {
      const files = this._pendingFiles || []
      this._pendingFiles = null
      if (!files.length) return

      this.uploading = true; this.uploadProgress = 0
      const fd = new FormData()
      files.forEach(f => fd.append('files', f))
      try {
        const res = await axios.post(`${BACKEND_URL}/api/batch_upload`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: e => {
            if (e.total) this.uploadProgress = Math.round(e.loaded / e.total * 100)
          },
        })
        if (res.data.count > 0) {
          ElMessage.success(`成功上传 ${res.data.count} 张图像`)
          this.currentPage = 1
          this.loadImages()
        }
        res.data.errors?.forEach(err => ElMessage.warning(err))
      } catch (err) {
        ElMessage.error('上传失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.uploading = false; this.uploadProgress = 0
      }
    },

    sendToBatch() {
      if (!this.selectedIds.length) return
      const selected = this.images.filter(i => this.selectedIds.includes(i.image_id))
      sessionStorage.setItem('library_selected_files', JSON.stringify(selected))
      ElMessage.success(`已将 ${selected.length} 张图像发送到批量处理`)
      this.$router.push('/batch')
    },

    async confirmDelete() {
      try {
        await ElMessageBox.confirm(
          `确认删除选中的 ${this.selectedIds.length} 张原始图像及其全部加密产物？此操作不可恢复。`,
          '确认删除', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
        )
      } catch { return }
      try {
        const res = await axios.post(`${BACKEND_URL}/api/image_library/delete`,
          { image_ids: this.selectedIds })
        ElMessage.success(`已删除 ${res.data.deleted_count} 条记录`)
        this.selectedIds = []
        this.loadImages()
      } catch (err) {
        ElMessage.error('删除失败: ' + (err.response?.data?.error || err.message))
      }
    },

    async confirmClean() {
      try {
        await ElMessageBox.confirm(
          '清理所有加密/解密中间产物（数据库记录 + 磁盘文件），原始图像完全不受影响。确认继续？',
          '清理中间产物', { type: 'warning', confirmButtonText: '确认清理', cancelButtonText: '取消' }
        )
      } catch { return }
      try {
        const res = await axios.post(`${BACKEND_URL}/api/image_library/clean`)
        ElMessage.success(
          `清理完成：${res.data.deleted_images} 条图像记录、` +
          `${res.data.deleted_analysis} 条分析记录、` +
          `${res.data.file_deleted ?? 0} 个文件`
        )
      } catch (err) {
        ElMessage.error('清理失败: ' + (err.response?.data?.error || err.message))
      }
    },
  },
}
</script>

<style scoped>
.library-page { display: flex; flex-direction: column; gap: 12px; }

/* 工具栏 */
.lib-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  padding: 10px 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.select-count {
  font-size: 12px;
  color: #4f6ef7;
  background: #f0f2ff;
  border-radius: 10px;
  padding: 2px 8px;
}
.lib-total { font-size: 13px; color: #606266; }

/* 图像网格容器 */
.grid-container {
  min-height: 300px;
  position: relative;
}
.empty-state {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

/* 网格 */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}

/* 网格项 */
.grid-item {
  background: #fff;
  border: 2px solid #e4e7ed;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.grid-item:hover {
  border-color: #4f6ef7;
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(79,110,247,0.15);
}
.grid-item.selected {
  border-color: #4f6ef7;
  background: #f5f7ff;
}

/* 选中标记 */
.item-check {
  position: absolute;
  top: 6px; right: 6px;
  z-index: 2;
  width: 20px; height: 20px;
  display: flex; align-items: center; justify-content: center;
}
.check-ring {
  width: 18px; height: 18px;
  border: 2px solid rgba(200,200,200,0.9);
  border-radius: 50%;
  background: rgba(255,255,255,0.6);
}

/* 缩略图区 */
.thumb-area {
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f7fa, #eef0f5);
  overflow: hidden;
}
.thumb-img {
  max-width: 100%; max-height: 100%;
  object-fit: contain;
}
.thumb-loading {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 信息 */
.item-info {
  padding: 6px 8px;
  border-top: 1px solid #f0f0f0;
}
.item-name {
  font-size: 12px; font-weight: 500; color: #303133;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.item-meta {
  display: flex; justify-content: space-between;
  font-size: 10px; color: #909399; margin-top: 2px;
}

/* 分页 */
.pagination-bar {
  display: flex;
  justify-content: center;
  padding: 8px 0;
}
</style>