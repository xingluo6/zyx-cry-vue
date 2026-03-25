<template>
  <el-card class="box-card" style="margin-top: 20px">
    <template #header>
      <div class="card-header">
        <span>统计图表</span>
      </div>
    </template>
    <div
      v-if="!analysisResults"
      style="
        text-align: center;
        color: #909399;
        height: 300px;
        line-height: 300px;
      "
    >
      运行分析后显示图表
    </div>
    <div v-else>
      <el-row :gutter="20">
        <el-col :span="12">
          <div ref="histogramChart" class="chart-container"></div>
        </el-col>
        <el-col :span="12">
          <div ref="correlationChart" class="chart-container"></div>
        </el-col>
        <el-col :span="12">
          <div ref="scoreChart" class="chart-container"></div>
        </el-col>
        <el-col :span="12">
          <div ref="entropyChart" class="chart-container"></div>
        </el-col>
      </el-row>
    </div>
  </el-card>
</template>

<script>
import * as echarts from "echarts";

export default {
  name: "AnalysisCharts",
  props: {
    analysisResults: {
      type: Object,
      default: null,
    },
  },
  data() {
    return {
      // 将图表实例存储在data中，移除下划线
      histogramChartInstance: null,
      correlationChartInstance: null,
      scoreChartInstance: null,
      entropyChartInstance: null,
    };
  },
  watch: {
    analysisResults: {
      handler(newResults) {
        if (newResults) {
          // 当有新数据时，确保DOM已更新，然后绘制图表
          this.$nextTick(() => {
            this.initAndDrawCharts(newResults);
          });
        } else {
          // 当数据为null时，清除图表
          this.clearCharts();
        }
      },
      deep: true,
      immediate: true, // 立即执行一次，处理初始状态
    },
  },
  mounted() {
    // 在 mounted 钩子中，只添加窗口resize监听器
    window.addEventListener("resize", this.resizeCharts);
  },
  beforeUnmount() {
    // 销毁图表实例和事件监听器
    window.removeEventListener("resize", this.resizeCharts);
    this.clearCharts(); // 确保组件销毁时清除图表
  },
  methods: {
    initAndDrawCharts(results) {
      if (!results) {
        this.clearCharts();
        return;
      }

      // 确保DOM元素存在再初始化ECharts
      if (!this.histogramChartInstance && this.$refs.histogramChart) {
        this.histogramChartInstance = echarts.init(this.$refs.histogramChart);
      }
      if (!this.correlationChartInstance && this.$refs.correlationChart) {
        this.correlationChartInstance = echarts.init(
          this.$refs.correlationChart
        );
      }
      if (!this.scoreChartInstance && this.$refs.scoreChart) {
        this.scoreChartInstance = echarts.init(this.$refs.scoreChart);
      }
      if (!this.entropyChartInstance && this.$refs.entropyChart) {
        this.entropyChartInstance = echarts.init(this.$refs.entropyChart);
      }

      // 1. 直方图对比 (只取加密图像的灰度直方图，如果不存在则取B通道)
      const histogramData =
        results.histogram_encrypted.gray || results.histogram_encrypted.b;
      if (this.histogramChartInstance && histogramData) {
        const histogramOption = {
          title: { text: "加密图像直方图", left: "center" },
          tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
          xAxis: {
            type: "category",
            data: Array.from({ length: 256 }, (_, i) => i),
          },
          yAxis: { type: "value" },
          series: [
            {
              name: "像素频数",
              type: "bar",
              data: histogramData,
              itemStyle: { color: "#91cc75" },
            },
          ],
        };
        this.histogramChartInstance.setOption(histogramOption);
      }

      // 2. 像素相关性对比
      if (this.correlationChartInstance) {
        const correlationOption = {
          title: { text: "像素相关性对比", left: "center" },
          tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
          xAxis: { type: "category", data: ["水平", "垂直", "对角"] },
          yAxis: { type: "value", min: -1, max: 1 },
          legend: { data: ["原始图像", "加密图像"], bottom: 0 },
          series: [
            {
              name: "原始图像",
              type: "bar",
              data: [
                results.correlation_h_original,
                results.correlation_v_original,
                results.correlation_d_original,
              ],
              itemStyle: { color: "#5470c6" },
            },
            {
              name: "加密图像",
              type: "bar",
              data: [
                results.correlation_h_encrypted,
                results.correlation_v_encrypted,
                results.correlation_d_encrypted,
              ],
              itemStyle: { color: "#ee6666" },
            },
          ],
        };
        this.correlationChartInstance.setOption(correlationOption);
      }

      // 3. 综合安全性评分
      if (this.scoreChartInstance) {
        const scoreOption = {
          title: { text: "综合安全性评分", left: "center" },
          tooltip: { formatter: "{b}: {c}/100" },
          xAxis: { type: "value", min: 0, max: 100 },
          yAxis: { type: "category", data: ["评分"] },
          series: [
            {
              name: "评分",
              type: "bar",
              data: [results.security_score],
              itemStyle: {
                color: (params) => {
                  const score = params.value;
                  if (score >= 80) return "#67C23A"; // 优秀
                  if (score >= 65) return "#E6A23C"; // 良好
                  if (score >= 50) return "#F56C6C"; // 中等
                  return "#909399"; // 较差
                },
              },
            },
          ],
        };
        this.scoreChartInstance.setOption(scoreOption);
      }

      // 4. 信息熵对比
      if (this.entropyChartInstance) {
        const entropyOption = {
          title: { text: "信息熵对比", left: "center" },
          tooltip: { trigger: "axis" },
          xAxis: { type: "category", data: ["原始图像", "加密图像"] },
          yAxis: { type: "value", min: 0, max: 8 },
          series: [
            {
              name: "信息熵",
              type: "bar",
              data: [results.entropy_original, results.entropy_encrypted],
              itemStyle: {
                color: (params) => {
                  if (params.name === "加密图像" && params.value > 7.5)
                    return "#67C23A";
                  if (params.name === "加密图像" && params.value > 7.0)
                    return "#E6A23C";
                  return "#5470c6";
                },
              },
            },
          ],
        };
        this.entropyChartInstance.setOption(entropyOption);
      }

      this.resizeCharts(); // 绘制后调整大小
    },
    clearCharts() {
      // 销毁所有图表实例
      if (this.histogramChartInstance) {
        this.histogramChartInstance.dispose();
        this.histogramChartInstance = null;
      }
      if (this.correlationChartInstance) {
        this.correlationChartInstance.dispose();
        this.correlationChartInstance = null;
      }
      if (this.scoreChartInstance) {
        this.scoreChartInstance.dispose();
        this.scoreChartInstance = null;
      }
      if (this.entropyChartInstance) {
        this.entropyChartInstance.dispose();
        this.entropyChartInstance = null;
      }
    },
    resizeCharts() {
      // 调整所有图表的大小
      if (this.histogramChartInstance) this.histogramChartInstance.resize();
      if (this.correlationChartInstance) this.correlationChartInstance.resize();
      if (this.scoreChartInstance) this.scoreChartInstance.resize();
      if (this.entropyChartInstance) this.entropyChartInstance.resize();
    },
  },
};
</script>

<style scoped>
.chart-container {
  width: 100%;
  height: 300px; /* 固定图表高度 */
  margin-bottom: 20px;
}
</style>
