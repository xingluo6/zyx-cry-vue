<template>
  <el-form :model="params" label-width="120px" size="small">

    <!-- Arnold变换 -->
    <template v-if="algorithm === 'Arnold变换'">
      <el-form-item label="迭代次数">
        <el-input-number v-model="params.iterations" :min="1" :max="100" style="width:100%" />
      </el-form-item>
      <el-alert title="Arnold 变换说明"
        description="通过坐标置换打乱像素位置。迭代次数存在周期性，过多反而还原原图。"
        type="info" :closable="false" show-icon />
    </template>

    <!-- XOR加密 -->
    <template v-else-if="algorithm === 'XOR加密'">
      <el-form-item label="加密密钥">
        <el-input v-model="params.key" placeholder="输入字符串密钥" />
      </el-form-item>
      <el-form-item label="加密模式">
        <el-radio-group v-model="params.xor_mode">
          <el-radio label="string">字符串密钥</el-radio>
          <el-radio label="byte">单字节密钥</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="字节值" v-if="params.xor_mode === 'byte'">
        <el-input-number v-model="params.xor_byte" :min="0" :max="255" style="width:100%" />
      </el-form-item>
    </template>

    <!-- XXTEA加密 -->
    <template v-else-if="algorithm === 'XXTEA加密'">
      <el-form-item label="加密密钥">
        <el-input v-model="params.key" placeholder="输入密钥字符串" />
      </el-form-item>
    </template>

    <!-- AES加密 -->
    <template v-else-if="algorithm === 'AES加密'">
      <el-form-item label="AES密钥">
        <el-input v-model="params.key" placeholder="自动填充/截断到 16/24/32 字节" />
      </el-form-item>
      <el-form-item label="加密模式">
        <el-select v-model="params.mode" style="width:100%">
          <el-option label="CFB（推荐）" value="CFB" />
          <el-option label="CBC"         value="CBC" />
          <el-option label="OFB"         value="OFB" />
          <el-option label="ECB（不安全，仅演示）" value="ECB" />
        </el-select>
      </el-form-item>
      <el-alert v-if="params.mode === 'ECB'"
        title="⚠️ ECB 模式存在严重安全隐患"
        description="相同明文块产生相同密文块，会泄露图像结构。仅用于教学演示，生产请用 CFB/CBC/OFB。"
        type="error" :closable="false" show-icon style="margin-top:4px" />
      <el-alert v-else-if="params.mode === 'CFB'"
        title="CFB 模式（推荐）：流密码模式，无需填充，适合图像加密。"
        type="success" :closable="false" show-icon style="margin-top:4px" />
    </template>

    <!-- Logistic混沌加密 -->
    <template v-else-if="algorithm === 'Logistic混沌加密'">
      <el-form-item label="加密密钥">
        <el-input v-model="params.key_string" placeholder="密钥字符串，派生 r 和 x₀" />
      </el-form-item>
      <el-form-item label="参数来源">
        <el-checkbox v-model="params.use_key_params">使用密钥自动派生 r 和 x₀</el-checkbox>
      </el-form-item>
      <template v-if="!params.use_key_params">
        <el-form-item label="r 值 (3.57~4.0)">
          <el-input-number v-model="params.r"
            :min="3.570001" :max="4.0" :precision="6" :step="0.000001" style="width:100%" />
        </el-form-item>
        <el-form-item label="x₀ 值 (0~1)">
          <el-input-number v-model="params.x0"
            :min="0.000001" :max="0.999999" :precision="6" :step="0.000001" style="width:100%" />
        </el-form-item>
      </template>
      <el-form-item label="预热迭代次数">
        <el-input-number v-model="params.discard_iterations" :min="1" :max="1000" style="width:100%" />
      </el-form-item>
    </template>

    <!-- 🆕 AES-GCM加密 -->
    <template v-else-if="algorithm === 'AES-GCM加密'">
      <el-form-item label="加密密钥">
        <el-input v-model="params.key_string" placeholder="输入密钥字符串" />
      </el-form-item>
      <el-alert
        title="AES-256-GCM（现代认证加密）"
        description="GCM 模式同时提供机密性和完整性保护（带 Auth Tag），是 TLS 1.3 的默认模式。比传统 AES-CBC/CFB 更安全，支持硬件加速。"
        type="success" :closable="false" show-icon />
    </template>

    <!-- 🆕 ChaCha20加密 -->
    <template v-else-if="algorithm === 'ChaCha20加密'">
      <el-form-item label="加密密钥">
        <el-input v-model="params.key_string" placeholder="输入密钥字符串" />
      </el-form-item>
      <el-alert
        title="ChaCha20-Poly1305（Google 推动的流密码）"
        description="无需硬件加速即可达到 AES-NI 同等性能，移动端首选。Poly1305 提供 MAC 认证，被 Android/iOS/Chrome 广泛使用（RFC 8439）。"
        type="success" :closable="false" show-icon />
    </template>

    <!-- 🆕 RSA混合加密 -->
    <template v-else-if="algorithm === 'RSA混合加密'">
      <el-form-item label="密钥标识">
        <el-input v-model="params.key_string" placeholder="输入密钥标识字符串" />
      </el-form-item>
      <el-alert
        title="RSA-2048 混合加密（数字信封）"
        description="非对称 + 对称混合架构：RSA-OAEP 加密随机 AES 会话密钥，AES-256-GCM 加密实际图像数据。这是 HTTPS/TLS 握手的核心思想。"
        type="warning" :closable="false" show-icon />
      <el-alert
        description="⚠️ RSA 密钥生成较耗时（~1s），处理大图时请耐心等待。"
        type="info" :closable="false" style="margin-top:4px" />
    </template>

    <!-- 未选择 -->
    <template v-else>
      <el-form-item>
        <el-alert type="info" :closable="false" title="请先选择一个加密算法" />
      </el-form-item>
    </template>

  </el-form>
</template>

<script>
export default {
  name: 'AlgorithmParamsForm',
  props: {
    algorithm:  { type: String, required: true },
    modelValue: { type: Object, required: true },
  },
  computed: {
    params: {
      get()      { return this.modelValue },
      set(value) { this.$emit('update:modelValue', value) },
    },
  },
  watch: {
    algorithm: { handler(a) { this.resetParams(a) }, immediate: true },
  },
  methods: {
    resetParams(algo) {
      const defaults = {
        'Arnold变换':       { iterations: 10 },
        'XOR加密':          { key: 'default_xor_key', xor_mode: 'string', xor_byte: 23 },
        'XXTEA加密':        { key: 'default_xxtea_key' },
        'AES加密':          { key: 'default_aes_key', mode: 'CFB' },
        'Logistic混沌加密': { key_string: 'default_logistic_key', use_key_params: true,
                              r: 3.99, x0: 0.01, discard_iterations: 100 },
        'AES-GCM加密':      { key_string: 'default_aesgcm_key' },
        'ChaCha20加密':     { key_string: 'default_chacha20_key' },
        'RSA混合加密':      { key_string: 'default_rsa_key' },
      }
      this.$emit('update:modelValue', Object.assign({}, defaults[algo] ?? {}))
    },
  },
}
</script>

<style scoped>
.el-form-item { margin-bottom: 12px; }
.el-alert { font-size: 12px; }
</style>
