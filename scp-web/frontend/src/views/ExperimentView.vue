<template>
  <div class="exp-page">

    <!-- 顶部说明 -->
    <el-alert type="info" :closable="false" style="margin-bottom:16px">
      <template #title>实验对比分析</template>
      <template #default>
        基于 MongoDB 中的历史分析记录，按算法统计各指标的
        <b>均值 ± 标准差</b>，生成论文格式的横向对比表格。
        数据越多，统计结果越稳定可靠。
      </template>
    </el-alert>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <span class="filter-label">算法筛选：</span>
      <el-checkbox-group v-model="selectedAlgos" size="small">
        <el-checkbox-button v-for="a in availableAlgos" :key="a" :label="a">
          {{ a }}
        </el-checkbox-button>
      </el-checkbox-group>
      <el-button size="small" @click="selectedAlgos = availableAlgos.slice()">全选</el-button>
      <el-button size="small" @click="selectedAlgos = []">清空</el-button>

      <div style="margin-left:auto;display:flex;gap:8px">
        <el-button type="primary" size="small" :loading="loading" @click="fetchData">
          <el-icon><refresh /></el-icon>&nbsp;刷新数据
        </el-button>
        <!-- ✅ 导出 PDF 按钮 -->
        <el-button type="danger" plain size="small"
          @click="exportPDF" :loading="exportingPDF"
          :disabled="tableData.length === 0">
          <el-icon><document /></el-icon>&nbsp;导出实验报告 PDF
        </el-button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading" size="36" color="#4f6ef7"><loading /></el-icon>
      <div style="margin-top:10px;color:#909399">正在汇总数据...</div>
    </div>

    <!-- 无数据 -->
    <el-empty
      v-else-if="!loading && tableData.length === 0"
      description="暂无数据，请先在批量处理或单算法页面运行分析"
      :image-size="100"
      style="margin-top:40px"
    />

    <!-- 结果区域 -->
    <template v-else>

      <!-- 汇总卡片 -->
      <el-row :gutter="12" style="margin-bottom:16px">
        <el-col :span="6">
          <el-card shadow="never" class="summary-mini">
            <div class="mini-val">{{ tableData.length }}</div>
            <div class="mini-label">参与对比算法数</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="summary-mini">
            <div class="mini-val">{{ totalSamples }}</div>
            <div class="mini-label">总样本数（条）</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="summary-mini">
            <div class="mini-val" style="color:#67C23A">{{ bestAlgo }}</div>
            <div class="mini-label">综合评分最高算法</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="summary-mini">
            <div class="mini-val" style="color:#5470c6">{{ fastestAlgo }}</div>
            <div class="mini-label">加密速度最快算法</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 主对比表格（论文风格） -->
      <el-card>
        <template #header>
          <div class="card-header">
            <span>算法性能横向对比（均值 ± 标准差）</span>
            <div style="display:flex;gap:8px">
              <el-tag size="small" type="info">样本总量 {{ totalSamples }} 条</el-tag>
            </div>
          </div>
        </template>

        <div class="table-caption">
          表 1&nbsp; 各图像加密算法安全性与性能指标对比
          <span class="table-note">（↑ 越大越好，↓ 越小越好）</span>
        </div>

        <el-table :data="tableData" border stripe size="small"
          class="paper-table" header-row-class-name="paper-header">

          <el-table-column prop="algorithm" label="算法" width="148" fixed>
            <template #default="{ row }">
              <div class="algo-cell">
                <span class="algo-name">{{ row.algorithm }}</span>
                <el-tag size="small" type="info" style="font-size:10px">n={{ row.count }}</el-tag>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="安全评分↑" width="110" align="center">
            <template #header>
              <div class="col-header">安全评分<br><span class="unit">（0-100，↑）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell" :class="isBest(row,'security_score') ? 'best' : ''">
                {{ ms(row.metrics.security_score) }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="信息熵↑" width="120" align="center">
            <template #header>
              <div class="col-header">信息熵<br><span class="unit">（bit，↑&gt;7.9）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell" :class="isBest(row,'entropy_encrypted') ? 'best' : ''">
                {{ ms(row.metrics.entropy_encrypted, 4) }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="NPCR(%)↑" width="120" align="center">
            <template #header>
              <div class="col-header">NPCR<br><span class="unit">（%，↑&gt;99.6）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell" :class="isBest(row,'npcr') ? 'best' : ''">
                {{ ms(row.metrics.npcr, 3) }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="UACI(%)≈33.46" width="128" align="center">
            <template #header>
              <div class="col-header">UACI<br><span class="unit">（%，≈33.46 最优）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell" :class="isClosest(row,'uaci',33.46) ? 'best' : ''">
                {{ ms(row.metrics.uaci, 3) }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="PSNR(dB)↓" width="116" align="center">
            <template #header>
              <div class="col-header">PSNR<br><span class="unit">（dB，↓越低越好）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell" :class="isWorst(row,'psnr') ? 'best' : ''">
                {{ ms(row.metrics.psnr, 2) }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="ARL↓" width="104" align="center">
            <template #header>
              <div class="col-header">ARL<br><span class="unit">（↓&lt;2.0 优秀）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell" :class="isWorst(row,'arl_encrypted') ? 'best' : ''">
                {{ ms(row.metrics.arl_encrypted, 3) }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="卡方检验↓" width="118" align="center">
            <template #header>
              <div class="col-header">卡方检验<br><span class="unit">（↓&lt;1000 优秀）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell" :class="isWorst(row,'chi2_encrypted') ? 'best' : ''">
                {{ ms(row.metrics.chi2_encrypted, 1) }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="相关性↓" width="108" align="center">
            <template #header>
              <div class="col-header">水平相关性<br><span class="unit">（↓越小越好）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell">
                {{ ms(row.metrics.correlation_h_encrypted, 4) }}
              </div>
            </template>
          </el-table-column>

          <el-table-column label="耗时(ms)↓" width="110" align="center">
            <template #header>
              <div class="col-header">加密耗时<br><span class="unit">（ms，↓越快越好）</span></div>
            </template>
            <template #default="{ row }">
              <div class="ms-cell" :class="isWorst(row,'encrypt_time_ms') ? 'best' : ''">
                {{ ms(row.metrics.encrypt_time_ms, 1) }}
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="table-footnote">
          注：表中数据格式为「均值 ± 标准差」。
          <span class="best-note">绿色背景</span>表示该指标最优值。
          样本来源于历史分析记录，数据量越大结果越可靠。
        </div>
      </el-card>

      <!-- 可视化图表 -->
      <el-card style="margin-top:16px">
        <template #header><span>算法综合性能可视化</span></template>
        <el-row :gutter="20">
          <el-col :span="12">
            <div ref="radarChart" style="width:100%;height:340px"></div>
          </el-col>
          <el-col :span="12">
            <div ref="barChart" style="width:100%;height:340px"></div>
          </el-col>
        </el-row>
      </el-card>

    </template>

  </div>
</template>

<script>
import axios from 'axios'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { Refresh, Loading, Document } from '@element-plus/icons-vue'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? ''

const ALGO_COLORS = {
  'Arnold变换':          '#5470c6',
  'XOR加密':             '#91cc75',
  'XXTEA加密':           '#fac858',
  'AES加密':             '#ee6666',
  'Logistic混沌加密':    '#73c0de',
  'AES-GCM加密':         '#3ba272',
  'ChaCha20加密':        '#fc8452',
  'RSA混合加密':         '#9a60b4',
  'Combined Encryption': '#ea7ccc',
}
const DEFAULT_COLORS = Object.values(ALGO_COLORS)
const algoColor = (name, idx=0) => ALGO_COLORS[name] ?? DEFAULT_COLORS[idx % DEFAULT_COLORS.length]

export default {
  name: 'ExperimentView',
  components: { Refresh, Loading, Document },

  data() {
    return {
      loading:      false,
      rawData:      [],
      availableAlgos: [],
      selectedAlgos:  [],
      charts:       {},
      // ✅ 导出
      exportingPDF: false,
    }
  },

  computed: {
    tableData() {
      if (!this.selectedAlgos.length) return this.rawData
      return this.rawData.filter(r => this.selectedAlgos.includes(r.algorithm))
    },
    totalSamples() {
      return this.tableData.reduce((s, r) => s + r.count, 0)
    },
    bestAlgo() {
      if (!this.tableData.length) return '-'
      const best = [...this.tableData].sort(
        (a,b) => (b.metrics.security_score?.mean ?? 0) - (a.metrics.security_score?.mean ?? 0)
      )[0]
      const name = best?.algorithm ?? '-'
      return name.length > 8 ? name.slice(0,8)+'…' : name
    },
    fastestAlgo() {
      if (!this.tableData.length) return '-'
      const fastest = [...this.tableData].sort(
        (a,b) => (a.metrics.encrypt_time_ms?.mean ?? 9999) - (b.metrics.encrypt_time_ms?.mean ?? 9999)
      )[0]
      const name = fastest?.algorithm ?? '-'
      return name.length > 8 ? name.slice(0,8)+'…' : name
    },
  },

  watch: {
    tableData: {
      handler() { this.$nextTick(() => setTimeout(() => this.drawCharts(), 80)) },
      deep: true,
    },
  },

  mounted() {
    this.fetchData()
    window.addEventListener('resize', this.resizeCharts)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.resizeCharts)
    Object.values(this.charts).forEach(c => c?.dispose())
  },

  methods: {
    async fetchData() {
      this.loading = true
      try {
        const res = await axios.post(`${BACKEND_URL}/api/experiment/stats`, {
          algorithm_names: this.selectedAlgos.length ? this.selectedAlgos : null
        })
        this.rawData        = res.data
        this.availableAlgos = res.data.map(r => r.algorithm)
        if (!this.selectedAlgos.length) {
          this.selectedAlgos = this.availableAlgos.slice()
        }
      } catch (err) {
        ElMessage.error('加载失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.loading = false
      }
    },

    // ✅ 导出实验报告 PDF
    async exportPDF() {
      this.exportingPDF = true
      try {
        const res = await axios.post(
          `${BACKEND_URL}/api/export/experiment_pdf`,
          { algorithm_names: this.selectedAlgos.length ? this.selectedAlgos : null },
          { responseType: 'blob' }
        )
        const url  = URL.createObjectURL(res.data)
        const a    = document.createElement('a')
        const date = new Date().toISOString().slice(0, 10)
        a.href = url; a.download = `实验对比报告_${date}.pdf`
        document.body.appendChild(a); a.click()
        document.body.removeChild(a); URL.revokeObjectURL(url)
        ElMessage.success('PDF 报告导出成功')
      } catch (err) {
        ElMessage.error('导出失败: ' + (err.response?.data?.error || err.message))
      } finally {
        this.exportingPDF = false
      }
    },

    // ── 表格辅助 ──
    ms(obj, digits = 2) {
      if (!obj) return '-'
      const m = obj.mean; const s = obj.std
      if (m === undefined || m === null) return '-'
      return `${Number(m).toFixed(digits)} ± ${Number(s ?? 0).toFixed(digits)}`
    },

    isBest(row, key) {
      const means = this.tableData.map(r => r.metrics[key]?.mean ?? -Infinity)
      const max   = Math.max(...means)
      return (row.metrics[key]?.mean ?? -Infinity) === max
    },
    isWorst(row, key) {
      const means = this.tableData.map(r => r.metrics[key]?.mean ?? Infinity)
      const min   = Math.min(...means)
      return (row.metrics[key]?.mean ?? Infinity) === min
    },
    isClosest(row, key, target) {
      const diffs   = this.tableData.map(r => Math.abs((r.metrics[key]?.mean ?? 999) - target))
      const minDiff = Math.min(...diffs)
      return Math.abs((row.metrics[key]?.mean ?? 999) - target) === minDiff
    },

    // ── 图表 ──
    getChart(ref) {
      const el = this.$refs[ref]
      if (!el) return null
      if (!this.charts[ref]) this.charts[ref] = echarts.init(el)
      return this.charts[ref]
    },

    drawCharts() {
      this.drawRadar()
      this.drawBar()
    },

    drawRadar() {
      const chart = this.getChart('radarChart')
      if (!chart || !this.tableData.length) return
      const indicators = [
        { name: '安全评分',  max: 100 },
        { name: '信息熵',    max: 100 },
        { name: 'NPCR',     max: 100 },
        { name: 'UACI适配', max: 100 },
        { name: '卡方均匀', max: 100 },
      ]
      const seriesData = this.tableData.map((r, idx) => ({
        name:  r.algorithm,
        value: [
          r.metrics.security_score?.mean ?? 0,
          Math.min(100, (r.metrics.entropy_encrypted?.mean ?? 0) * 12),
          r.metrics.npcr?.mean ?? 0,
          Math.max(0, 100 - Math.abs((r.metrics.uaci?.mean ?? 0) - 33.46) * 10),
          Math.max(0, Math.min(100, 100 - (r.metrics.chi2_encrypted?.mean ?? 500) / 100)),
        ],
        lineStyle: { color: algoColor(r.algorithm, idx) },
        itemStyle: { color: algoColor(r.algorithm, idx) },
        areaStyle: { opacity: 0.06 },
      }))
      chart.setOption({
        title:   { text: '综合能力雷达图', left: 'center', textStyle: { fontSize: 13 } },
        tooltip: { trigger: 'item', confine: false, appendToBody: true },
        legend:  { data: this.tableData.map(r => r.algorithm), bottom: 0, textStyle: { fontSize: 10 } },
        radar:   { indicator: indicators, radius: '58%', name: { textStyle: { fontSize: 11 } } },
        series:  [{ type: 'radar', data: seriesData }],
      })
    },

    drawBar() {
      const chart = this.getChart('barChart')
      if (!chart || !this.tableData.length) return
      const algos  = this.tableData.map(r => r.algorithm)
      const scores = this.tableData.map(r => ({
        value: r.metrics.security_score?.mean ?? 0,
        itemStyle: { color: algoColor(r.algorithm) },
      }))
      const times = this.tableData.map(r => r.metrics.encrypt_time_ms?.mean ?? 0)
      chart.setOption({
        title:   { text: '安全评分 vs 加密耗时', left: 'center', textStyle: { fontSize: 13 } },
        tooltip: { trigger: 'axis' },
        legend:  { data: ['安全评分', '耗时(ms)'], bottom: 0, textStyle: { fontSize: 11 } },
        grid:    { left: 50, right: 50, top: 40, bottom: 55 },
        xAxis:   { type: 'category', data: algos,
                   axisLabel: { fontSize: 10, rotate: 15, overflow: 'truncate', width: 72 } },
        yAxis: [
          { type: 'value', name: '评分', min: 0, max: 100, position: 'left' },
          { type: 'value', name: 'ms',              position: 'right', splitLine: { show: false } },
        ],
        series: [
          { name: '安全评分', type: 'bar', yAxisIndex: 0, data: scores, barMaxWidth: 36,
            label: { show: true, position: 'top', fontSize: 10 } },
          { name: '耗时(ms)', type: 'line', yAxisIndex: 1, data: times,
            smooth: true, symbol: 'circle', symbolSize: 6,
            lineStyle: { color: '#fc8452', width: 2 }, itemStyle: { color: '#fc8452' } },
        ],
      })
    },

    resizeCharts() {
      Object.values(this.charts).forEach(c => c?.resize())
    },
  },
}
</script>

<style scoped>
.exp-page { display: flex; flex-direction: column; gap: 0; }

.filter-bar {
  display: flex; align-items: center; flex-wrap: wrap;
  gap: 8px; background: #fff;
  border: 1px solid #e4e7ed; border-radius: 10px;
  padding: 10px 16px; margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.filter-label { font-size: 13px; color: #606266; white-space: nowrap; }

.summary-mini :deep(.el-card__body) { padding: 12px 16px !important; text-align: center; }
.mini-val   { font-size: 22px; font-weight: 700; color: #1a1f36; line-height: 1.2; }
.mini-label { font-size: 11px; color: #909399; margin-top: 4px; }

.table-caption {
  text-align: center; font-size: 13px; font-weight: 600;
  color: #303133; margin-bottom: 10px;
}
.table-note { font-size: 11px; color: #909399; font-weight: normal; margin-left: 8px; }

.paper-table :deep(.paper-header th) {
  background: #f0f2f5 !important; font-weight: 700 !important;
  font-size: 12px !important; text-align: center !important;
}
.col-header { font-size: 11px; line-height: 1.4; text-align: center; }
.unit       { font-size: 10px; color: #909399; font-weight: normal; }

.algo-cell {
  display: flex; align-items: center; justify-content: space-between;
  gap: 4px; font-size: 12px; font-weight: 500;
}
.algo-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.ms-cell {
  font-size: 11px; color: #303133;
  font-family: 'SFMono-Regular', Consolas, monospace;
  padding: 2px 4px; border-radius: 3px;
  white-space: nowrap;
}
.ms-cell.best {
  background: #f0f9eb; color: #389e0d; font-weight: 600;
}

.table-footnote {
  margin-top: 10px; font-size: 11px; color: #909399;
  padding: 6px 8px; background: #fafafa; border-radius: 6px;
}
.best-note {
  display: inline-block;
  background: #f0f9eb; color: #389e0d;
  padding: 1px 6px; border-radius: 3px; font-size: 11px;
}

.loading-state {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; padding: 60px 0;
}

.card-header {
  font-weight: 600; display: flex;
  justify-content: space-between; align-items: center;
}
</style>
