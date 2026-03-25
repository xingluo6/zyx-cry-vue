<template>
  <div class="dashboard-page">

    <!-- ── 顶部数字卡片 ── -->
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-inner">
            <div class="stat-icon" :style="{ background: card.bg }">
              <el-icon :size="26" :color="card.color">
                <component :is="card.icon" />
              </el-icon>
            </div>
            <div class="stat-body">
              <div class="stat-value">{{ card.value ?? '-' }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ── 工具栏 ── -->
    <div class="dash-toolbar">
      <el-button size="small" @click="fetchAll" :loading="loading">
        <el-icon><refresh /></el-icon>&nbsp;刷新数据
      </el-button>

      <el-divider direction="vertical" />

      <span class="toolbar-label">
        推荐模型：
        <el-tag :type="modelExists ? 'success' : 'warning'" size="small">
          {{ modelExists ? '已训练' : '未训练' }}
        </el-tag>
      </span>

      <el-button type="primary" size="small" :loading="trainingModel" @click="trainModel">
        <el-icon><magic-stick /></el-icon>&nbsp;{{ trainingModel ? '训练中...' : '训练推荐模型' }}
      </el-button>

      <el-tag v-if="trainResult"
        :type="trainResult.success ? 'success' : 'danger'"
        size="small"
        style="max-width:300px;white-space:normal;height:auto;line-height:1.5;padding:3px 8px">
        {{ trainResult.message }}
        <span v-if="trainResult.accuracy">
          （准确率 {{ (trainResult.accuracy*100).toFixed(1) }}%）
        </span>
      </el-tag>

      <el-divider direction="vertical" />

      <el-button type="danger" plain size="small" @click="showCleanDialog = true">
        <el-icon><delete /></el-icon>&nbsp;清理分析记录
      </el-button>

      <el-divider direction="vertical" />

      <el-button size="small" type="success" plain
        @click="exportExcel" :loading="exporting">
        <el-icon><download /></el-icon>&nbsp;导出 Excel
      </el-button>
    </div>

    <!-- ── 加载中 ── -->
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading" size="40" color="#4f6ef7"><loading /></el-icon>
      <div style="margin-top:12px;color:#909399;font-size:13px">正在加载数据...</div>
    </div>

    <!-- ── 无数据提示 ── -->
    <el-alert
      v-else-if="!loading && algoStats.length === 0"
      style="margin-top:16px"
      type="info"
      show-icon
      :closable="false"
    >
      <template #title>暂无分析数据</template>
      <template #default>
        请先在「单算法演示」页面上传图像并加密（已开启自动分析），
        或在「批量处理」页面运行批量分析。数据将自动汇聚到此处。
      </template>
    </el-alert>

    <!-- ── 图表区域（有数据才渲染） ── -->
    <template v-else>
      <DashboardCharts
        :algo-stats="algoStats"
        :score-trend="scoreTrend"
        style="margin-top:16px"
      />

      <!-- ── 最近记录表格 ── -->
      <el-card style="margin-top:16px">
        <template #header>
          <div class="card-header">
            <span>最近分析记录</span>
            <el-tag type="info" size="small">最近 {{ recentRecords.length }} 条</el-tag>
          </div>
        </template>
        <el-table :data="recentRecords" border stripe size="small" max-height="320">
          <el-table-column prop="original_filename" label="文件名"
            min-width="110" show-overflow-tooltip />
          <el-table-column prop="algorithm" label="算法"
            width="148" show-overflow-tooltip />
          <el-table-column label="安全评分" width="88" align="center">
            <template #default="{ row }">
              <el-tag :type="scoreTag(row.security_score)" size="small">
                {{ row.security_score }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="信息熵" width="78" align="right">
            <template #default="{ row }">{{ n(row.metrics?.entropy_encrypted, 4) }}</template>
          </el-table-column>
          <el-table-column label="NPCR(%)" width="82" align="right">
            <template #default="{ row }">{{ n(row.metrics?.npcr, 3) }}</template>
          </el-table-column>
          <el-table-column label="UACI(%)" width="82" align="right">
            <template #default="{ row }">{{ n(row.metrics?.uaci, 3) }}</template>
          </el-table-column>
          <el-table-column label="分析时间" width="140" align="center">
            <template #default="{ row }">{{ fmt(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <!-- ── 分析记录清理对话框 ── -->
    <el-dialog v-model="showCleanDialog" title="清理分析记录"
      width="460px" :close-on-click-modal="false">

      <el-form label-width="90px" size="small">
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="cleanDateRange" type="daterange"
            range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期"
            format="YYYY-MM-DD" value-format="YYYY-MM-DD" style="width:100%"
            :shortcuts="dateShortcuts"
          />
        </el-form-item>
        <el-form-item label="算法筛选">
          <el-select v-model="cleanAlgorithm" clearable
            placeholder="全部算法" style="width:100%">
            <el-option v-for="a in knownAlgos" :key="a" :label="a" :value="a" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-alert :title="cleanPreviewText" type="warning"
        :closable="false" show-icon style="margin-bottom:8px" />
      <el-alert title="此操作不可恢复，清理后大屏数据同步更新。"
        type="error" :closable="false" show-icon />

      <template #footer>
        <el-button @click="showCleanDialog = false">取消</el-button>
        <el-button type="danger" :loading="cleaning" @click="doClean">确认清理</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import DashboardCharts from '@/components/DashboardCharts.vue'
import {
  PictureFilled, DataAnalysis, Cpu, Trophy,
  Loading, Refresh, MagicStick, Delete, Download,
} from '@element-plus/icons-vue'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? ''

export default {
  name: 'DashboardView',
  components: {
    DashboardCharts,
    PictureFilled, DataAnalysis, Cpu, Trophy,
    Loading, Refresh, MagicStick, Delete, Download,
  },

  data() {
    return {
      loading:       true,
      counts:        {},
      algoStats:     [],
      scoreTrend:    [],
      recentRecords: [],

      modelExists:   false,
      trainingModel: false,
      trainResult:   null,
      exporting:     false,

      showCleanDialog: false,
      cleanDateRange:  [],
      cleanAlgorithm:  '',
      cleaning:        false,

      knownAlgos: [
        'Arnold变换','XOR加密','XXTEA加密','AES加密',
        'Logistic混沌加密','Combined Encryption',
      ],
      dateShortcuts: [
        { text: '最近一周', value: () => { const e=new Date(),s=new Date(); s.setDate(s.getDate()-7);  return [s,e] } },
        { text: '最近一月', value: () => { const e=new Date(),s=new Date(); s.setMonth(s.getMonth()-1); return [s,e] } },
        { text: '最近三月', value: () => { const e=new Date(),s=new Date(); s.setMonth(s.getMonth()-3); return [s,e] } },
        { text: '全部',     value: () => [new Date('2020-01-01'), new Date()] },
      ],
    }
  },

  computed: {
    statCards() {
      const best = this.algoStats.length ? this.algoStats[0].algorithm : '-'
      const bestShort = best.length > 7 ? best.slice(0,7)+'…' : best
      return [
        { label:'上传图像总数', value: this.counts.image_count,    icon:'PictureFilled', bg:'#ecf5ff', color:'#409EFF' },
        { label:'累计分析次数', value: this.counts.analysis_count,  icon:'DataAnalysis',  bg:'#f0f9eb', color:'#67C23A' },
        { label:'涉及算法种类', value: this.counts.algo_count,      icon:'Cpu',           bg:'#fdf6ec', color:'#E6A23C' },
        { label:'最高评分算法', value: bestShort,                   icon:'Trophy',        bg:'#fef0f0', color:'#F56C6C' },
      ]
    },
    cleanPreviewText() {
      const dr = (this.cleanDateRange?.length === 2)
        ? `${this.cleanDateRange[0]} 至 ${this.cleanDateRange[1]}`
        : '全部'
      const al = this.cleanAlgorithm || '全部'
      return `清理范围 — 日期：${dr}，算法：${al}`
    },
  },

  mounted() {
    this.fetchAll()
    this.checkModel()
  },

  methods: {
    async fetchAll() {
      this.loading = true
      try {
        const [a, b, c, d] = await Promise.all([
          axios.get(`${BACKEND_URL}/api/dashboard/stats`),
          axios.get(`${BACKEND_URL}/api/dashboard/algorithm_stats`),
          axios.get(`${BACKEND_URL}/api/dashboard/score_trend?limit=60`),
          axios.get(`${BACKEND_URL}/api/dashboard/recent?limit=20`),
        ])
        this.counts        = a.data
        this.algoStats     = b.data
        this.scoreTrend    = c.data
        this.recentRecords = d.data
      } catch (err) {
        ElMessage.error('数据加载失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.loading = false
      }
    },

    async checkModel() {
      try {
        const res    = await axios.get(`${BACKEND_URL}/api/recommend/status`)
        this.modelExists = res.data.model_exists ?? false
      } catch { this.modelExists = false }
    },

    async trainModel() {
      this.trainingModel = true; this.trainResult = null
      try {
        const res    = await axios.post(`${BACKEND_URL}/api/recommend/train`)
        this.trainResult = res.data
        this.modelExists = res.data.success ?? false
        if (res.data.success) ElMessage.success('推荐模型训练成功！')
        else                   ElMessage.warning(res.data.message)
      } catch (err) {
        ElMessage.error('训练失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.trainingModel = false
      }
    },

    async doClean() {
      if (!this.cleanDateRange?.length && !this.cleanAlgorithm) {
        try {
          await ElMessageBox.confirm(
            '未设置任何筛选条件，将清空【全部】分析记录，确认继续？',
            '危险操作',
            { type: 'error', confirmButtonText: '确认清空全部', cancelButtonText: '取消' }
          )
        } catch { return }
      }
      this.cleaning = true
      try {
        const payload = {}
        if (this.cleanDateRange?.length === 2) {
          payload.start_date = this.cleanDateRange[0]
          payload.end_date   = this.cleanDateRange[1]
        }
        if (this.cleanAlgorithm) payload.algorithm = this.cleanAlgorithm
        const res = await axios.post(`${BACKEND_URL}/api/analysis/delete`, payload)
        ElMessage.success(`已清理 ${res.data.deleted_count} 条分析记录`)
        this.showCleanDialog = false
        this.cleanDateRange  = []
        this.cleanAlgorithm  = ''
        this.fetchAll()
      } catch (err) {
        ElMessage.error('清理失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.cleaning = false
      }
    },

    exportExcel() {
      this.exporting = true
      const url = `${BACKEND_URL}/api/export/dashboard_excel`
      const a   = document.createElement('a')
      a.href = url; a.target = '_blank'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      ElMessage.success('Excel 导出中，请查看下载文件')
      setTimeout(() => { this.exporting = false }, 2000)
    },

    scoreTag(s) {
      if (s >= 80) return 'success'
      if (s >= 65) return 'warning'
      if (s >= 50) return 'danger'
      return 'info'
    },
    n(v, d=3) {
      if (v === undefined || v === null) return '-'
      return Number(v).toFixed(d)
    },
    fmt(v) { return v ? String(v).slice(0,16) : '-' },
  },
}
</script>

<style scoped>
.dashboard-page { display:flex; flex-direction:column; gap:0; }

/* ── 数字卡片 ── */
.stat-card :deep(.el-card__body) {
  padding: 14px 18px !important;
}
.stat-inner {
  display: flex; align-items: center; gap: 14px;
}
.stat-icon {
  width: 48px; height: 48px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.stat-body  { flex: 1; min-width: 0; }
.stat-value {
  font-size: 24px; font-weight: 700; color: #1a1f36;
  line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.stat-label { font-size: 12px; color: #909399; margin-top: 2px; }

/* ── 工具栏 ── */
.dash-toolbar {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  background: #fff; border: 1px solid #e4e7ed; border-radius: 10px;
  padding: 10px 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  margin-bottom: 4px;
}
.toolbar-label { font-size: 13px; color: #606266; }

/* ── 加载中 ── */
.loading-state {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; padding: 60px 0;
}

/* ── 卡片头部 ── */
.card-header {
  font-weight: 600; display: flex;
  justify-content: space-between; align-items: center;
}
</style>