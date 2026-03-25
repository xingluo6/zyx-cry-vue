<template>
  <div>
    <!-- 汇总统计卡片 -->
    <el-row :gutter="16" class="summary-row" v-if="summary.length > 0">
      <el-col
        v-for="item in summary"
        :key="item.algorithm"
        :xs="12" :sm="12" :md="8" :lg="Math.floor(24 / summary.length)"
        style="margin-bottom: 12px"
      >
        <el-card shadow="hover" class="summary-card">
          <div class="algo-name" :title="item.algorithm">{{ item.algorithm }}</div>
          <div class="algo-score" :class="scoreClass(item.avg_score)">
            {{ item.avg_score }}<span class="score-unit"> 分</span>
          </div>
          <div class="algo-meta">
            <div>⏱ {{ item.avg_time_ms }} ms</div>
            <div>熵 {{ item.avg_entropy }}</div>
            <div>NPCR {{ item.avg_npcr }}%</div>
          </div>
          <div class="algo-count">共 {{ item.count }} 张</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 对比图表：挂载后立即渲染，不依赖 v-if 切换 -->
    <el-row :gutter="16" style="margin-top: 16px" v-if="summary.length > 0">
      <el-col :span="12">
        <el-card>
          <div ref="scoreChart" style="width:100%;height:280px"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <div ref="timeChart" style="width:100%;height:280px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 明细表格 -->
    <el-card style="margin-top: 16px" v-if="tableData.length > 0">
      <template #header>
        <div class="card-header">
          <span>逐条明细</span>
          <div style="display:flex;gap:8px">
            <el-select
              v-model="filterAlgo"
              placeholder="筛选算法"
              clearable
              size="small"
              style="width:160px"
            >
              <el-option v-for="a in algoOptions" :key="a" :label="a" :value="a" />
            </el-select>
            <el-input
              v-model="filterFile"
              placeholder="搜索文件名"
              clearable
              size="small"
              style="width:160px"
            />
          </div>
        </div>
      </template>

      <el-table
        :data="filteredData"
        border
        stripe
        size="small"
        max-height="460"
      >
        <el-table-column prop="original_filename" label="文件名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="algorithm" label="算法" width="140" show-overflow-tooltip />
        <el-table-column label="安全评分" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="scoreTagType(row.security_score)" size="small">
              {{ row.security_score }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="encrypt_time_ms" label="耗时(ms)" width="90" align="right" />
        <el-table-column label="信息熵" width="80" align="right">
          <template #default="{ row }">{{ fmtN(row.metrics?.entropy_encrypted, 4) }}</template>
        </el-table-column>
        <el-table-column label="NPCR(%)" width="88" align="right">
          <template #default="{ row }">{{ fmtN(row.metrics?.npcr, 3) }}</template>
        </el-table-column>
        <el-table-column label="UACI(%)" width="88" align="right">
          <template #default="{ row }">{{ fmtN(row.metrics?.uaci, 3) }}</template>
        </el-table-column>
        <el-table-column label="PSNR(dB)" width="88" align="right">
          <template #default="{ row }">{{ fmtN(row.metrics?.psnr, 2) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="64" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.success" color="#67C23A"><circle-check /></el-icon>
            <el-tooltip v-else :content="row.error" placement="top">
              <el-icon color="#F56C6C"><circle-close /></el-icon>
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        共 {{ filteredData.length }} 条（成功 {{ successCount }}，失败 {{ failedCount }}）
      </div>
    </el-card>
  </div>
</template>

<script>
import * as echarts from 'echarts'
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'

export default {
  name: 'BatchResultTable',
  components: { CircleCheck, CircleClose },

  props: {
    batchResult: { type: Object, default: null },
  },

  data() {
    return {
      filterAlgo: '',
      filterFile: '',
      scoreChartInstance: null,
      timeChartInstance:  null,
    }
  },

  computed: {
    summary()  { return this.batchResult?.summary  ?? [] },
    tableData() {
      return (this.batchResult?.results ?? []).map(r => ({
        ...r,
        encrypt_time_ms: r.encrypt_time_ms ?? 0,
      }))
    },
    algoOptions() {
      return [...new Set(this.tableData.map(r => r.algorithm))]
    },
    filteredData() {
      return this.tableData.filter(r => {
        const algoOk = !this.filterAlgo || r.algorithm === this.filterAlgo
        const fileOk = !this.filterFile ||
          (r.original_filename ?? '').toLowerCase().includes(this.filterFile.toLowerCase())
        return algoOk && fileOk
      })
    },
    successCount() { return this.tableData.filter(r =>  r.success).length },
    failedCount()  { return this.tableData.filter(r => !r.success).length },
  },

  watch: {
    // summary 数据就绪后，等 DOM 渲染完再画图
    summary: {
      handler(val) {
        if (val && val.length > 0) {
          this.$nextTick(() => {
            // 再等一帧，确保 el-card 内的 div 已有实际尺寸
            setTimeout(() => this.drawCharts(), 100)
          })
        } else {
          this.disposeCharts()
        }
      },
      immediate: false,
    },
  },

  mounted() {
    window.addEventListener('resize', this.resizeCharts)
    // 如果 props 传入时组件已挂载（父组件 v-if 切换场景）
    if (this.summary.length > 0) {
      this.$nextTick(() => setTimeout(() => this.drawCharts(), 100))
    }
  },

  beforeUnmount() {
    window.removeEventListener('resize', this.resizeCharts)
    this.disposeCharts()
  },

  methods: {
    drawCharts() {
      const algos  = this.summary.map(s => s.algorithm)
      const scores = this.summary.map(s => s.avg_score)
      const times  = this.summary.map(s => s.avg_time_ms)

      // ── 安全评分柱状图 ──
      const scoreEl = this.$refs.scoreChart
      if (scoreEl) {
        if (!this.scoreChartInstance) {
          this.scoreChartInstance = echarts.init(scoreEl)
        }
        this.scoreChartInstance.setOption({
          title: { text: '平均安全评分对比', left: 'center', textStyle: { fontSize: 13 } },
          tooltip: { trigger: 'axis' },
          grid: { bottom: 60 },
          xAxis: {
            type: 'category',
            data: algos,
            axisLabel: { fontSize: 11, rotate: 15, overflow: 'truncate', width: 80 },
          },
          yAxis: { type: 'value', min: 0, max: 100, name: '分' },
          series: [{
            type: 'bar',
            data: scores,
            barMaxWidth: 48,
            label: { show: true, position: 'top', fontSize: 11 },
            itemStyle: {
              color: p => {
                const v = p.value
                if (v >= 80) return '#67C23A'
                if (v >= 65) return '#E6A23C'
                if (v >= 50) return '#F56C6C'
                return '#909399'
              },
            },
          }],
        })
      }

      // ── 加密耗时柱状图 ──
      const timeEl = this.$refs.timeChart
      if (timeEl) {
        if (!this.timeChartInstance) {
          this.timeChartInstance = echarts.init(timeEl)
        }
        this.timeChartInstance.setOption({
          title: { text: '平均加密耗时对比', left: 'center', textStyle: { fontSize: 13 } },
          tooltip: { trigger: 'axis', formatter: '{b}: {c} ms' },
          grid: { bottom: 60 },
          xAxis: {
            type: 'category',
            data: algos,
            axisLabel: { fontSize: 11, rotate: 15, overflow: 'truncate', width: 80 },
          },
          yAxis: { type: 'value', name: 'ms' },
          series: [{
            type: 'bar',
            data: times,
            barMaxWidth: 48,
            label: { show: true, position: 'top', fontSize: 11, formatter: '{c}ms' },
            itemStyle: { color: '#5470c6' },
          }],
        })
      }

      this.resizeCharts()
    },

    resizeCharts() {
      this.scoreChartInstance?.resize()
      this.timeChartInstance?.resize()
    },

    disposeCharts() {
      this.scoreChartInstance?.dispose()
      this.scoreChartInstance = null
      this.timeChartInstance?.dispose()
      this.timeChartInstance = null
    },

    scoreClass(score) {
      if (score >= 80) return 'score-excellent'
      if (score >= 65) return 'score-good'
      if (score >= 50) return 'score-medium'
      return 'score-poor'
    },
    scoreTagType(score) {
      if (score >= 80) return 'success'
      if (score >= 65) return 'warning'
      if (score >= 50) return 'danger'
      return 'info'
    },
    fmtN(val, digits = 3) {
      if (val === undefined || val === null) return '-'
      return Number(val).toFixed(digits)
    },
  },
}
</script>

<style scoped>
/* 汇总卡片：固定高度 + flex 居中，保证各卡片等高对齐 */
.summary-card {
  height: 160px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 8px 4px;
  box-sizing: border-box;
}
.algo-name {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 4px;
}
.algo-score {
  font-size: 30px;
  font-weight: bold;
  line-height: 1.1;
}
.score-unit    { font-size: 13px; font-weight: normal; }
.score-excellent { color: #67C23A; }
.score-good      { color: #E6A23C; }
.score-medium    { color: #F56C6C; }
.score-poor      { color: #909399; }

/* 指标行：竖向排列，每项独占一行 */
.algo-meta {
  margin-top: 8px;
  font-size: 11px;
  color: #909399;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  line-height: 1.5;
}
.algo-count {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
}
.card-header {
  font-weight: bold;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.table-footer {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
  text-align: right;
}
</style>