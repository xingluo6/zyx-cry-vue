<template>
  <div class="batch-page">
    <el-row :gutter="20">

      <!-- 左侧：配置面板 -->
      <el-col :span="7">

        <!-- 模式提示 -->
        <el-alert v-if="celeryAvailable !== null"
          :type="celeryAvailable ? 'success' : 'info'"
          :closable="false"
          style="margin-bottom:10px;font-size:12px"
        >
          <template #title>
            {{ celeryAvailable
              ? '⚡ 异步模式：处理期间可继续操作页面'
              : '🔄 同步模式：等待处理完成后返回结果' }}
          </template>
        </el-alert>

        <!-- 图像来源 -->
        <el-card>
          <template #header>
            <div class="card-header"><span>图像来源</span></div>
          </template>

          <BatchUploader @uploaded="onUploaded" />

          <el-divider content-position="center" style="margin:12px 0">
            <span style="font-size:12px;color:#909399">或</span>
          </el-divider>

          <el-button style="width:100%" type="success" plain size="small"
            :loading="importingLibrary" @click="importFromLibrary">
            <el-icon><folder-opened /></el-icon>&nbsp;
            从图像库导入全部图片（{{ libraryTotal }} 张）
          </el-button>
        </el-card>

        <!-- 待处理列表 -->
        <el-card style="margin-top:10px" v-if="uploadedImages.length > 0">
          <template #header>
            <div class="card-header">
              <span>待处理图片</span>
              <div style="display:flex;gap:6px;align-items:center">
                <el-tag type="success" size="small">{{ uploadedImages.length }} 张</el-tag>
                <el-button type="danger" link size="small" @click="uploadedImages = []">
                  清空
                </el-button>
              </div>
            </div>
          </template>
          <div class="image-chips">
            <el-tag v-for="img in uploadedImages" :key="img.image_id"
              closable size="small" @close="removeUploadedImage(img.image_id)">
              {{ img.filename }}
            </el-tag>
          </div>
          <el-alert v-if="fromLibrary" title="图像来自图像库" type="info"
            :closable="true" show-icon style="margin-top:8px;font-size:12px"
            @close="fromLibrary = false" />
        </el-card>

        <!-- 算法选择 -->
        <el-card style="margin-top:10px">
          <template #header>
            <div class="card-header">
              <span>选择算法</span>
              <el-button type="primary" link size="small" @click="selectAllAlgos">全选</el-button>
            </div>
          </template>

          <div style="margin-bottom:8px">
            <div style="font-size:11px;color:#909399;margin-bottom:6px">传统加密</div>
            <el-checkbox-group v-model="selectedAlgoNames">
              <div v-for="algo in classicAlgos" :key="algo.name" class="algo-checkbox">
                <el-checkbox :label="algo.name">{{ algo.label }}</el-checkbox>
              </div>
            </el-checkbox-group>
          </div>

          <el-divider style="margin:6px 0" />

          <div>
            <div style="font-size:11px;color:#909399;margin-bottom:6px">现代加密（推荐）</div>
            <el-checkbox-group v-model="selectedAlgoNames">
              <div v-for="algo in modernAlgos" :key="algo.name" class="algo-checkbox">
                <el-checkbox :label="algo.name">{{ algo.label }}</el-checkbox>
              </div>
            </el-checkbox-group>
          </div>

          <el-divider style="margin:6px 0" />

          <el-form label-width="90px" size="small">
            <el-form-item label="并发线程数">
              <el-input-number v-model="maxWorkers" :min="1" :max="8" style="width:100%" />
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 增量模式 -->
        <el-card style="margin-top:10px">
          <div class="incremental-row">
            <el-checkbox v-model="incrementalMode" size="small">
              <span style="font-weight:500">增量模式</span>
            </el-checkbox>
            <el-tooltip placement="top" :show-after="200">
              <template #content>
                跳过「同一图片 × 同一算法」已处理过的组合，只补充缺失的分析记录。
              </template>
              <el-icon color="#909399" style="cursor:help;margin-left:4px">
                <question-filled />
              </el-icon>
            </el-tooltip>
          </div>
          <div v-if="incrementalMode" class="incremental-hint">
            将跳过「图片×算法」已有分析记录的组合，只处理缺失部分
          </div>
          <div v-if="incrementalMode && analyzedCount > 0" class="analyzed-stats">
            <el-icon color="#67C23A"><circle-check /></el-icon>
            数据库已有 <b>{{ analyzedCount }}</b> 条分析记录
          </div>
        </el-card>

        <!-- 执行按钮 -->
        <el-card style="margin-top:10px">
          <el-button type="primary" style="width:100%" size="large"
            :loading="isSubmitting"
            :disabled="uploadedImages.length === 0 || selectedAlgoNames.length === 0 || isPolling"
            @click="startBatchProcess">
            {{ isSubmitting ? '提交中...' : isPolling ? '处理中（异步）...' : '开始批量处理' }}
          </el-button>

          <div v-if="!isSubmitting && !isPolling
                      && uploadedImages.length > 0 && selectedAlgoNames.length > 0"
            class="estimate-hint">
            预计 {{ uploadedImages.length }} × {{ selectedAlgoNames.length }} =
            {{ uploadedImages.length * selectedAlgoNames.length }} 个任务
            <span v-if="incrementalMode" style="color:#E6A23C">
              （增量模式下将跳过已有记录）
            </span>
          </div>
        </el-card>

      </el-col>

      <!-- 右侧：进度 + 结果 -->
      <el-col :span="17">

        <!-- 异步进度面板 -->
        <TaskProgressPanel
          v-if="taskId"
          style="margin-bottom:14px"
          :task-id="taskId"
          :state="taskState"
          :percent="taskPercent"
          :current="taskCurrent"
          :total="taskTotal"
          :success="taskSuccess"
          :failed="taskFailed"
          :status-text="taskStatus"
          :start-time="taskStartTime"
          @cancel="cancelTask"
        />

        <!-- 同步进度条（无 Celery 时） -->
        <el-card v-if="syncProcessing" style="margin-bottom:14px">
          <div style="font-size:13px;color:#606266;margin-bottom:10px">
            <el-icon class="is-loading" style="margin-right:4px"><loading /></el-icon>
            批量处理中，请稍候...
            <span style="font-size:11px;color:#909399;margin-left:8px">
              图片较多时可能需要数分钟
            </span>
          </div>
          <el-progress :percentage="syncProgress" :stroke-width="10" />
        </el-card>

        <!-- 空状态 -->
        <el-empty
          v-if="!taskId && !syncProcessing && !batchResult"
          description="配置图像来源和算法后，点击「开始批量处理」"
          :image-size="160"
          style="margin-top:60px"
        />

        <!-- 导出 + 结果表 -->
        <template v-if="batchResult">
          <div class="export-bar">
            <el-button size="small" type="success"
              @click="exportBatchExcel" :loading="exporting">
              <el-icon><download /></el-icon>&nbsp;导出本次结果 Excel
            </el-button>
            <span style="font-size:11px;color:#909399">
              包含算法汇总和逐条明细两个工作表
            </span>
          </div>
          <BatchResultTable :batch-result="batchResult" />
        </template>

      </el-col>

    </el-row>
  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import BatchUploader      from '@/components/BatchUploader.vue'
import BatchResultTable   from '@/components/BatchResultTable.vue'
import TaskProgressPanel  from '@/components/TaskProgressPanel.vue'
import {
  FolderOpened, QuestionFilled, CircleCheck,
  Download, Loading,
} from '@element-plus/icons-vue'

const BACKEND_URL   = import.meta.env.VITE_BACKEND_URL ?? ''
const POLL_INTERVAL = 1500   // ms，轮询间隔

const CLASSIC_ALGOS = [
  { name: 'Arnold变换',       label: 'Arnold 变换' },
  { name: 'XOR加密',          label: 'XOR 加密' },
  { name: 'XXTEA加密',        label: 'XXTEA 加密' },
  { name: 'AES加密',          label: 'AES 加密' },
  { name: 'Logistic混沌加密', label: 'Logistic 混沌加密' },
]
const MODERN_ALGOS = [
  { name: 'AES-GCM加密',  label: 'AES-GCM（认证加密）' },
  { name: 'ChaCha20加密', label: 'ChaCha20（流密码）' },
  { name: 'RSA混合加密',  label: 'RSA 混合加密（较慢）' },
]

export default {
  name: 'BatchView',
  components: {
    BatchUploader, BatchResultTable, TaskProgressPanel,
    FolderOpened, QuestionFilled, CircleCheck, Download, Loading,
  },

  data() {
    return {
      // ── 图像来源 ──
      uploadedImages:    [],
      classicAlgos:      CLASSIC_ALGOS,
      modernAlgos:       MODERN_ALGOS,
      selectedAlgoNames: [...CLASSIC_ALGOS, ...MODERN_ALGOS].map(a => a.name),
      maxWorkers:        4,
      libraryTotal:      0,
      importingLibrary:  false,
      fromLibrary:       false,

      // ── 增量模式 ──
      incrementalMode: true,
      analyzedCount:   0,

      // ── Celery 状态 ──
      celeryAvailable: null,   // null=未检测, true/false

      // ── 异步任务（Celery 模式）──
      taskId:        '',
      taskState:     'PENDING',
      taskPercent:   0,
      taskCurrent:   0,
      taskTotal:     0,
      taskSuccess:   0,
      taskFailed:    0,
      taskStatus:    '',
      taskStartTime: 0,
      _pollTimer:    null,

      // ── 同步降级模式 ──
      syncProcessing: false,
      syncProgress:   0,

      // ── 结果 ──
      batchResult: null,
      exporting:   false,
    }
  },

  computed: {
    isSubmitting() { return this.syncProcessing && this.syncProgress === 0 },
    isPolling()    { return !!this._pollTimer },
  },

  activated() {
    this.checkLibraryTransfer()
    this.fetchLibraryTotal()
    if (this.incrementalMode) this.fetchAnalyzedCount()
  },

  mounted() {
    this.checkCelery()
    this.fetchLibraryTotal()
    this.fetchAnalyzedCount()
  },

  beforeUnmount() {
    this._stopPolling()
  },

  watch: {
    incrementalMode(val) { if (val) this.fetchAnalyzedCount() },
  },

  methods: {
    // ── Celery 检测 ──
    async checkCelery() {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/celery_status`, { timeout: 3000 })
        this.celeryAvailable = res.data.available ?? false
      } catch {
        this.celeryAvailable = false
      }
    },

    // ── 图像库 ──
    async fetchLibraryTotal() {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/image_library`,
          { params: { page: 1, page_size: 1 } })
        this.libraryTotal = res.data.total ?? 0
      } catch { this.libraryTotal = 0 }
    },

    async importFromLibrary() {
      if (this.libraryTotal === 0) {
        ElMessage.warning('图像库为空，请先上传图片'); return
      }
      this.importingLibrary = true
      try {
        const res    = await axios.get(`${BACKEND_URL}/api/image_library/all_ids`)
        const ids    = res.data ?? []
        if (!ids.length) { ElMessage.warning('图像库为空'); return }
        const libRes = await axios.get(`${BACKEND_URL}/api/image_library`,
          { params: { page: 1, page_size: 999 } })
        const imgMap = Object.fromEntries(
          (libRes.data.items ?? []).map(i => [i.image_id, i])
        )
        const toAdd = ids
          .filter(id => !this.uploadedImages.find(u => u.image_id === id))
          .map(id => ({
            image_id: id,
            filename: imgMap[id]?.filename ?? id,
            shape:    imgMap[id]?.shape ?? [],
          }))
        this.uploadedImages.push(...toAdd)
        this.fromLibrary = true
        ElMessage.success(`已从图像库导入 ${toAdd.length} 张图片`)
      } catch (err) {
        ElMessage.error('导入失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.importingLibrary = false
      }
    },

    async fetchAnalyzedCount() {
      try {
        const res = await axios.get(`${BACKEND_URL}/api/dashboard/stats`)
        this.analyzedCount = res.data.analysis_count ?? 0
      } catch { this.analyzedCount = 0 }
    },

    checkLibraryTransfer() {
      const raw = sessionStorage.getItem('library_selected_files')
      if (!raw) return
      try {
        const files = JSON.parse(raw)
        if (files?.length) {
          const existing = new Set(this.uploadedImages.map(i => i.image_id))
          files.forEach(f => { if (!existing.has(f.image_id)) this.uploadedImages.push(f) })
          this.fromLibrary = true
          ElMessage.success(`已从图像库导入 ${files.length} 张图像`)
          sessionStorage.removeItem('library_selected_files')
        }
      } catch { /* ignore */ }
    },

    // ── 上传回调 ──
    onUploaded(list) {
      this.uploadedImages.push(...list)
      const seen = new Set()
      this.uploadedImages = this.uploadedImages.filter(img => {
        if (seen.has(img.image_id)) return false
        seen.add(img.image_id); return true
      })
    },

    removeUploadedImage(id) {
      this.uploadedImages = this.uploadedImages.filter(i => i.image_id !== id)
    },

    selectAllAlgos() {
      this.selectedAlgoNames = [...CLASSIC_ALGOS, ...MODERN_ALGOS].map(a => a.name)
    },

    // ── 主处理流程 ──
    async startBatchProcess() {
      if (!this.uploadedImages.length) return ElMessage.warning('请先选择图片')
      if (!this.selectedAlgoNames.length) return ElMessage.warning('请至少选择一种算法')

      this.batchResult = null
      this._stopPolling()

      let imageIds  = this.uploadedImages.map(i => i.image_id)
      let algoNames = [...this.selectedAlgoNames]

      // 增量过滤（现在只是透传，后端兜底）
      if (this.incrementalMode) {
        const filtered = await this._filterIncremental(imageIds, algoNames)
        imageIds  = filtered.imageIds
        algoNames = filtered.algoNames
        // skippedCount 由后端实际统计，这里不再预判断
      }

      const payload = {
        image_ids:   imageIds,
        algorithms:  algoNames.map(name => ({ name, params: {} })),
        max_workers: this.maxWorkers,
        incremental: this.incrementalMode,  // ★ 传给后端，后端根据此参数决定是否跳过已有记录
      }

      try {
        const res = await axios.post(`${BACKEND_URL}/api/batch_process`, payload)

        if (res.status === 202 && res.data.mode === 'async') {
          // ── 异步模式：启动轮询 ──
          this.taskId        = res.data.task_id
          this.taskState     = 'PENDING'
          this.taskPercent   = 0
          this.taskCurrent   = 0
          this.taskTotal     = res.data.total ?? 0
          this.taskSuccess   = 0
          this.taskFailed    = 0
          this.taskStatus    = '任务已提交，等待 Worker 处理...'
          this.taskStartTime = Date.now()
          ElMessage.success('批量任务已提交，后台异步处理中')
          this._startPolling()
        } else {
          // ── 同步降级：直接拿结果 ──
          this.batchResult = res.data
          await this.fetchAnalyzedCount()
          ElMessage.success(
            `批量处理完成：${res.data.success} 成功，${res.data.failed} 失败`
          )
        }
      } catch (err) {
        ElMessage.error('提交失败: ' + (err.response?.data?.error || err.message))
      }
    },

    // ── 轮询 ──
    _startPolling() {
      this._pollTimer = setInterval(() => this._poll(), POLL_INTERVAL)
    },

    _stopPolling() {
      if (this._pollTimer) {
        clearInterval(this._pollTimer)
        this._pollTimer = null
      }
    },

    async _poll() {
      if (!this.taskId) { this._stopPolling(); return }
      try {
        const res  = await axios.get(`${BACKEND_URL}/api/task_status/${this.taskId}`)
        const data = res.data

        this.taskState   = data.state
        this.taskPercent = data.percent ?? 0
        this.taskCurrent = data.current ?? 0
        this.taskTotal   = data.total   ?? this.taskTotal
        this.taskSuccess = data.success ?? 0
        this.taskFailed  = data.failed  ?? 0
        this.taskStatus  = data.status  ?? ''

        if (data.state === 'SUCCESS') {
          this._stopPolling()
          const r = data.result ?? {}

          // ★ 修复 BackendStoreError：任务返回值已不含 results 明细
          //    （base64 + 直方图数组体积过大，超出 Redis 单 key 限制）
          //    改为任务完成后从 MongoDB 最近记录里补拉明细数据
          let recentRecords = []
          try {
            const recentRes = await axios.get(
              `${BACKEND_URL}/api/dashboard/recent`,
              { params: { limit: (r.total ?? 0) + 20 } }
            )
            recentRecords = (recentRes.data ?? []).map(rec => ({
              success:           true,
              algorithm:         rec.algorithm         ?? '',
              original_filename: rec.original_filename ?? '',
              security_score:    rec.security_score    ?? 0,
              encrypt_time_ms:   0,
              metrics:           rec.metrics           ?? {},
            }))
          } catch { /* 拉取失败不影响主流程，表格显示空 */ }

          this.batchResult = {
            total:   r.total   ?? 0,
            success: r.success ?? 0,
            failed:  r.failed  ?? 0,
            summary: r.summary ?? [],
            results: recentRecords,
          }

          await this.fetchAnalyzedCount()
          const skipped = r.skipped ?? 0
          ElMessage.success(
            `批量处理完成：${r.success ?? 0} 成功，${r.failed ?? 0} 失败` +
            (skipped > 0 ? `，增量模式跳过 ${skipped} 个已有记录` : '')
          )
        } else if (data.state === 'FAILURE') {
          this._stopPolling()
          ElMessage.error('批量处理失败: ' + (data.error ?? '未知错误'))
        }
      } catch (err) {
        // 网络偶发错误不停止轮询，最多容忍 5 次
        this._pollErrors = (this._pollErrors ?? 0) + 1
        if (this._pollErrors > 5) {
          this._stopPolling()
          ElMessage.error('轮询失败，请刷新页面查看结果')
        }
      }
    },

    async cancelTask() {
      if (!this.taskId) return
      try {
        await axios.post(`${BACKEND_URL}/api/task_cancel/${this.taskId}`)
        this._stopPolling()
        this.taskState  = 'FAILURE'
        this.taskStatus = '任务已取消'
        ElMessage.info('任务已取消')
      } catch (err) {
        ElMessage.error('取消失败: ' + err.message)
      }
    },

    // ── 增量过滤 ──
    async _filterIncremental(imageIds, algoNames) {
      // ★ 修复说明：
      //   旧版本在前端计算「每张图缺哪些算法」，再取并集传给后端。
      //   但后端 API 接收的是 imageIds × algoNames 的笛卡尔积，
      //   并集导致不同图片的已完成组合被重复处理。
      //
      // 新方案：前端不再做笛卡尔积预过滤。
      //   直接把全量 imageIds 和 algoNames 传给后端，
      //   由 tasks.py 的 _run_single_encrypt_analyze 在执行前
      //   精确查 MongoDB，已有记录则跳过（incremental=True 参数）。
      //   后端兜底 100% 准确，前端只负责展示跳过数量。
      return { imageIds, algoNames, skippedCount: 0 }
    },

    // ── 导出 ──
    async exportBatchExcel() {
      if (!this.batchResult) return
      this.exporting = true
      try {
        const res = await axios.post(
          `${BACKEND_URL}/api/export/batch_excel`,
          { batch_result: this.batchResult },
          { responseType: 'blob' }
        )
        const url  = URL.createObjectURL(res.data)
        const a    = document.createElement('a')
        a.href = url; a.download = `批量处理结果_${new Date().toISOString().slice(0,10)}.xlsx`
        document.body.appendChild(a); a.click()
        document.body.removeChild(a); URL.revokeObjectURL(url)
        ElMessage.success('Excel 导出成功')
      } catch (err) {
        ElMessage.error('导出失败: ' + err.message)
      } finally {
        this.exporting = false
      }
    },
  },
}
</script>

<style scoped>
.batch-page  { padding: 0; }
.card-header {
  font-weight: 600; display: flex;
  justify-content: space-between; align-items: center;
}
.image-chips {
  display: flex; flex-wrap: wrap; gap: 6px;
  max-height: 130px; overflow-y: auto;
}
.algo-checkbox { margin-bottom: 5px; }
.incremental-row { display: flex; align-items: center; gap: 4px; }
.incremental-hint {
  margin-top: 6px; font-size: 11px; color: #E6A23C;
  background: #fdf6ec; border-radius: 4px; padding: 4px 8px;
}
.analyzed-stats {
  margin-top: 6px; font-size: 12px; color: #606266;
  display: flex; align-items: center; gap: 4px;
}
.estimate-hint {
  margin-top: 8px; font-size: 11px; color: #909399; text-align: center;
}
.export-bar {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 12px; padding: 8px 14px;
  background: #f0f9eb; border-radius: 8px;
  border: 1px solid #d9f7be;
}
</style>