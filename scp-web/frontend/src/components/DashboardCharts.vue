<template>
  <div class="dashboard-charts">
    <el-row :gutter="20">

      <!-- 安全评分趋势折线图 -->
      <el-col :span="16">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>安全评分趋势</span>
              <el-tag size="small" type="info">最近 {{ scoreTrend.length }} 条记录</el-tag>
            </div>
          </template>
          <div ref="trendChart" class="chart-box-lg"></div>
        </el-card>
      </el-col>

      <!-- 算法平均评分雷达图 -->
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span>算法综合能力雷达</span>
          </template>
          <div ref="radarChart" class="chart-box-lg"></div>
        </el-card>
      </el-col>

    </el-row>

    <el-row :gutter="20" style="margin-top:20px">

      <!-- 算法平均指标柱状图 -->
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>各算法平均安全评分</span></template>
          <div ref="algoScoreChart" class="chart-box-md"></div>
        </el-card>
      </el-col>

      <!-- 算法平均信息熵 -->
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>各算法平均信息熵</span></template>
          <div ref="entropyChart" class="chart-box-md"></div>
        </el-card>
      </el-col>

    </el-row>

    <el-row :gutter="20" style="margin-top:20px">

      <!-- NPCR / UACI 对比组合图 -->
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>各算法 NPCR / UACI 对比</span></template>
          <div ref="npcruaciChart" class="chart-box-md"></div>
        </el-card>
      </el-col>

      <!-- 分析记录数量饼图（按算法占比） -->
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span>各算法分析次数占比</span></template>
          <div ref="pieChart" class="chart-box-md"></div>
        </el-card>
      </el-col>

    </el-row>
  </div>
</template>

<script>
import * as echarts from 'echarts'

// 固定颜色映射，保证同一算法在所有图表中颜色一致
const ALGO_COLORS = {
  'Arnold变换':       '#5470c6',
  'XOR加密':          '#91cc75',
  'XXTEA加密':        '#fac858',
  'AES加密':          '#ee6666',
  'Logistic混沌加密': '#73c0de',
  'Combined Encryption': '#3ba272',
}
const DEFAULT_COLORS = ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de','#3ba272','#fc8452']

function algoColor(name, idx = 0) {
  return ALGO_COLORS[name] ?? DEFAULT_COLORS[idx % DEFAULT_COLORS.length]
}

export default {
  name: 'DashboardCharts',

  props: {
    algoStats:   { type: Array,  default: () => [] },  // /api/dashboard/algorithm_stats
    scoreTrend:  { type: Array,  default: () => [] },  // /api/dashboard/score_trend
  },

  data() {
    return {
      charts: {},   // ref名 → echarts实例
    }
  },

  watch: {
    algoStats:  { handler() { this.$nextTick(() => setTimeout(() => this.drawAll(), 80)) }, deep: true },
    scoreTrend: { handler() { this.$nextTick(() => setTimeout(() => this.drawAll(), 80)) }, deep: true },
  },

  mounted() {
    window.addEventListener('resize', this.resizeAll)
    if (this.algoStats.length || this.scoreTrend.length) {
      this.$nextTick(() => setTimeout(() => this.drawAll(), 80))
    }
  },

  beforeUnmount() {
    window.removeEventListener('resize', this.resizeAll)
    Object.values(this.charts).forEach(c => c?.dispose())
    this.charts = {}
  },

  methods: {
    // 统一初始化/复用 echarts 实例
    getChart(refName) {
      const el = this.$refs[refName]
      if (!el) return null
      if (!this.charts[refName]) {
        this.charts[refName] = echarts.init(el)
      }
      return this.charts[refName]
    },

    drawAll() {
      this.drawTrendChart()
      this.drawRadarChart()
      this.drawAlgoScoreChart()
      this.drawEntropyChart()
      this.drawNpcrUaciChart()
      this.drawPieChart()
    },

    // ── 1. 安全评分趋势折线图 ──
    drawTrendChart() {
      const chart = this.getChart('trendChart')
      if (!chart || !this.scoreTrend.length) return

      // 按算法拆成多条折线
      const algoNames = [...new Set(this.scoreTrend.map(d => d.algorithm))]
      const timeLabels = this.scoreTrend.map(d => d.created_at.slice(5, 16))  // MM-DD HH:mm

      const series = algoNames.map((name, idx) => ({
        name,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2 },
        itemStyle: { color: algoColor(name, idx) },
        data: this.scoreTrend.map(d => d.algorithm === name ? d.score : null),
        connectNulls: false,
      }))

      chart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
        },
        legend: {
          data: algoNames,
          bottom: 0,
          textStyle: { fontSize: 11 },
        },
        grid: { left: 40, right: 20, top: 20, bottom: 60 },
        xAxis: {
          type: 'category',
          data: timeLabels,
          axisLabel: { fontSize: 10, rotate: 30 },
          boundaryGap: false,
        },
        yAxis: {
          type: 'value',
          min: 0, max: 100,
          name: '评分',
          nameTextStyle: { fontSize: 11 },
        },
        series,
      })
    },

    // ── 2. 算法综合能力雷达图 ──
    drawRadarChart() {
      const chart = this.getChart('radarChart')
      if (!chart || !this.algoStats.length) return

      const indicators = [
        { name: '安全评分',  max: 100  },
        { name: '信息熵×12', max: 100  },   // entropy * 12 映射到百分制
        { name: 'NPCR',     max: 100  },
        { name: 'UACI适配', max: 100  },   // 越接近33.46越高
        { name: '均匀性',   max: 100  },   // 100 - chi2/1000（上限100）
      ]

      const seriesData = this.algoStats.map((s, idx) => {
        const uaciScore  = Math.max(0, 100 - Math.abs((s.avg_uaci ?? 0) - 33.46) * 10)
        const chi2Score  = Math.max(0, Math.min(100, 100 - (s.avg_chi2 ?? 500) / 100))
        return {
          name:  s.algorithm,
          value: [
            s.avg_score,
            Math.min(100, (s.avg_entropy ?? 0) * 12),
            s.avg_npcr ?? 0,
            uaciScore,
            chi2Score,
          ],
          lineStyle:  { color: algoColor(s.algorithm, idx) },
          itemStyle:  { color: algoColor(s.algorithm, idx) },
          areaStyle:  { opacity: 0.08 },
        }
      })

      chart.setOption({
        tooltip: { trigger: 'item' },
        legend: {
          data: this.algoStats.map(s => s.algorithm),
          bottom: 0,
          textStyle: { fontSize: 10 },
        },
        radar: {
          indicator: indicators,
          radius: '62%',
          nameGap: 6,
          name: { textStyle: { fontSize: 11 } },
        },
        series: [{
          type: 'radar',
          data: seriesData,
        }],
      })
    },

    // ── 3. 各算法平均安全评分柱状图 ──
    drawAlgoScoreChart() {
      const chart = this.getChart('algoScoreChart')
      if (!chart || !this.algoStats.length) return

      const algos  = this.algoStats.map(s => s.algorithm)
      const scores = this.algoStats.map(s => s.avg_score)

      chart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 20, top: 30, bottom: 60 },
        xAxis: {
          type: 'category',
          data: algos,
          axisLabel: { fontSize: 10, rotate: 15, overflow: 'truncate', width: 72 },
        },
        yAxis: { type: 'value', min: 0, max: 100, name: '分' },
        series: [{
          type: 'bar',
          data: scores.map((v, i) => ({ value: v, itemStyle: { color: algoColor(algos[i], i) } })),
          barMaxWidth: 44,
          label: { show: true, position: 'top', fontSize: 11 },
        }],
      })
    },

    // ── 4. 各算法平均信息熵 ──
    drawEntropyChart() {
      const chart = this.getChart('entropyChart')
      if (!chart || !this.algoStats.length) return

      const algos    = this.algoStats.map(s => s.algorithm)
      const entropys = this.algoStats.map(s => s.avg_entropy)

      chart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 50, right: 20, top: 30, bottom: 60 },
        xAxis: {
          type: 'category',
          data: algos,
          axisLabel: { fontSize: 10, rotate: 15, overflow: 'truncate', width: 72 },
        },
        yAxis: { type: 'value', min: 6, max: 8.2, name: '信息熵' },
        // 参考线：7.9优秀线 / 7.5良好线
        markLine: {},
        series: [{
          type: 'bar',
          data: entropys.map((v, i) => ({ value: v, itemStyle: { color: algoColor(algos[i], i) } })),
          barMaxWidth: 44,
          label: { show: true, position: 'top', fontSize: 11, formatter: '{c}' },
          markLine: {
            silent: true,
            lineStyle: { type: 'dashed' },
            data: [
              { yAxis: 7.9, label: { formatter: '优秀线 7.9', fontSize: 10 }, lineStyle: { color: '#67C23A' } },
              { yAxis: 7.5, label: { formatter: '良好线 7.5', fontSize: 10 }, lineStyle: { color: '#E6A23C' } },
            ],
          },
        }],
      })
    },

    // ── 5. NPCR / UACI 对比组合图 ──
    drawNpcrUaciChart() {
      const chart = this.getChart('npcruaciChart')
      if (!chart || !this.algoStats.length) return

      const algos = this.algoStats.map(s => s.algorithm)
      const npcrs = this.algoStats.map(s => s.avg_npcr)
      const uacis = this.algoStats.map(s => s.avg_uaci)

      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['NPCR(%)', 'UACI(%)'], bottom: 0, textStyle: { fontSize: 11 } },
        grid: { left: 45, right: 20, top: 30, bottom: 55 },
        xAxis: {
          type: 'category',
          data: algos,
          axisLabel: { fontSize: 10, rotate: 15, overflow: 'truncate', width: 72 },
        },
        yAxis: [
          { type: 'value', name: 'NPCR(%)', min: 95, max: 100, position: 'left' },
          { type: 'value', name: 'UACI(%)', min: 20, max: 45,  position: 'right',
            splitLine: { show: false } },
        ],
        series: [
          {
            name: 'NPCR(%)',
            type: 'bar',
            yAxisIndex: 0,
            data: npcrs.map((v, i) => ({ value: v, itemStyle: { color: algoColor(algos[i], i) } })),
            barMaxWidth: 36,
            label: { show: true, position: 'top', fontSize: 10 },
          },
          {
            name: 'UACI(%)',
            type: 'line',
            yAxisIndex: 1,
            data: uacis,
            smooth: true,
            symbol: 'circle',
            symbolSize: 7,
            lineStyle: { color: '#fc8452', width: 2 },
            itemStyle: { color: '#fc8452' },
            // 理想值参考线
            markLine: {
              silent: true,
              data: [{ yAxis: 33.46, lineStyle: { color: '#909399', type: 'dashed' },
                       label: { formatter: '理想 33.46%', fontSize: 10 } }],
            },
          },
        ],
      })
    },

    // ── 6. 分析记录数量饼图 ──
    drawPieChart() {
      const chart = this.getChart('pieChart')
      if (!chart || !this.algoStats.length) return

      const pieData = this.algoStats.map((s, i) => ({
        name:      s.algorithm,
        value:     s.count,
        itemStyle: { color: algoColor(s.algorithm, i) },
      }))

      chart.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
        legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { fontSize: 11 } },
        series: [{
          type: 'pie',
          radius: ['40%', '68%'],
          center: ['40%', '50%'],
          avoidLabelOverlap: true,
          label: { show: false },
          emphasis: {
            label: { show: true, fontSize: 13, fontWeight: 'bold' },
          },
          data: pieData,
        }],
      })
    },

    resizeAll() {
      Object.values(this.charts).forEach(c => c?.resize())
    },
  },
}
</script>

<style scoped>
.chart-card { height: 100%; }
.chart-box-lg { width: 100%; height: 300px; }
.chart-box-md { width: 100%; height: 260px; }
.card-header {
  font-weight: bold;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
