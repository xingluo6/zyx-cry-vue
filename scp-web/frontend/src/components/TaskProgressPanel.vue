<template>
  <el-card class="progress-panel">
    <template #header>
      <div class="card-header">
        <span>批量处理进度</span>
        <div style="display:flex;gap:8px;align-items:center">
          <el-tag :type="stateTag" size="small">{{ stateLabel }}</el-tag>
          <el-button v-if="isRunning" size="small" type="danger" plain
            @click="$emit('cancel')">
            <el-icon><close /></el-icon>&nbsp;取消
          </el-button>
        </div>
      </div>
    </template>

    <!-- 主进度条 -->
    <el-progress
      :percentage="percent"
      :status="progressStatus"
      :stroke-width="14"
      :format="p => `${p}%`"
      style="margin-bottom:14px"
    />

    <!-- 统计数字 -->
    <el-row :gutter="12" style="margin-bottom:12px">
      <el-col :span="6">
        <div class="stat-mini">
          <div class="stat-num">{{ total }}</div>
          <div class="stat-label">总任务</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-mini">
          <div class="stat-num" style="color:#4f6ef7">{{ current }}</div>
          <div class="stat-label">已完成</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-mini">
          <div class="stat-num" style="color:#67C23A">{{ success }}</div>
          <div class="stat-label">成功</div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="stat-mini">
          <div class="stat-num" style="color:#F56C6C">{{ failed }}</div>
          <div class="stat-label">失败</div>
        </div>
      </el-col>
    </el-row>

    <!-- 状态文字 -->
    <div class="status-text">
      <el-icon v-if="isRunning" class="is-loading" style="margin-right:4px">
        <loading />
      </el-icon>
      <el-icon v-else-if="state === 'SUCCESS'" color="#67C23A" style="margin-right:4px">
        <circle-check-filled />
      </el-icon>
      <el-icon v-else-if="state === 'FAILURE'" color="#F56C6C" style="margin-right:4px">
        <circle-close-filled />
      </el-icon>
      {{ statusText }}
    </div>

    <!-- 耗时 -->
    <div v-if="elapsed > 0" class="elapsed-text">
      耗时：{{ elapsedStr }}
      <span v-if="isRunning && eta > 0">  预计剩余：{{ etaStr }}</span>
    </div>

    <!-- task_id（调试用，可折叠） -->
    <el-collapse style="margin-top:10px" v-if="taskId">
      <el-collapse-item name="id">
        <template #title>
          <span style="font-size:11px;color:#909399">任务 ID</span>
        </template>
        <div style="font-size:11px;color:#606266;word-break:break-all;
                    background:#f5f7fa;padding:6px 8px;border-radius:4px">
          {{ taskId }}
        </div>
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>

<script>
import {
  Close, Loading, CircleCheckFilled, CircleCloseFilled,
} from '@element-plus/icons-vue'

export default {
  name: 'TaskProgressPanel',
  components: { Close, Loading, CircleCheckFilled, CircleCloseFilled },
  emits: ['cancel'],

  props: {
    taskId:     { type: String,  default: '' },
    state:      { type: String,  default: 'PENDING' },
    percent:    { type: Number,  default: 0 },
    current:    { type: Number,  default: 0 },
    total:      { type: Number,  default: 0 },
    success:    { type: Number,  default: 0 },
    failed:     { type: Number,  default: 0 },
    statusText: { type: String,  default: '等待中...' },
    startTime:  { type: Number,  default: 0 },   // Date.now()
  },

  computed: {
    isRunning() {
      return ['PENDING','STARTED','PROGRESS'].includes(this.state)
    },
    stateTag() {
      const m = { PENDING:'info', STARTED:'primary', PROGRESS:'primary',
                  SUCCESS:'success', FAILURE:'danger' }
      return m[this.state] ?? 'info'
    },
    stateLabel() {
      const m = { PENDING:'等待中', STARTED:'已启动', PROGRESS:'处理中',
                  SUCCESS:'已完成', FAILURE:'处理失败' }
      return m[this.state] ?? this.state
    },
    progressStatus() {
      if (this.state === 'SUCCESS') return 'success'
      if (this.state === 'FAILURE') return 'exception'
      return ''
    },
    elapsed() {
      if (!this.startTime) return 0
      return Math.floor((Date.now() - this.startTime) / 1000)
    },
    elapsedStr() {
      const s = this.elapsed
      if (s < 60)  return `${s}s`
      return `${Math.floor(s/60)}m ${s%60}s`
    },
    eta() {
      if (!this.isRunning || !this.current || !this.total || !this.elapsed) return 0
      const rate      = this.current / this.elapsed   // tasks/sec
      const remaining = this.total - this.current
      return rate > 0 ? Math.ceil(remaining / rate) : 0
    },
    etaStr() {
      const s = this.eta
      if (s < 60)  return `${s}s`
      return `${Math.floor(s/60)}m ${s%60}s`
    },
  },
}
</script>

<style scoped>
.progress-panel :deep(.el-card__body) { padding: 14px 16px !important; }
.card-header {
  font-weight: 600; display: flex;
  justify-content: space-between; align-items: center;
}
.stat-mini { text-align: center; padding: 6px 0; }
.stat-num  { font-size: 20px; font-weight: 700; color: #1a1f36; line-height: 1.2; }
.stat-label { font-size: 11px; color: #909399; margin-top: 2px; }
.status-text {
  display: flex; align-items: center;
  font-size: 13px; color: #606266;
  background: #f5f7fa; border-radius: 6px; padding: 6px 10px;
}
.elapsed-text {
  margin-top: 6px; font-size: 11px; color: #909399; text-align: right;
}
</style>
