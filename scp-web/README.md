# 重构指南：从 Vue CLI → Vite

## 环境信息
- macOS Tahoe / MacBook Air M1
- Node v25.7.0
- Python 3.12.12 (Homebrew)

---

## 一、文件替换清单

### 需要替换/新建的文件（本目录已全部提供）

```
frontend/
├── package.json          ← 替换（Vue CLI → Vite）
├── vite.config.js        ← 新建（替代 vue.config.js，可删除旧的）
├── index.html            ← 新建（放在 frontend/ 根目录，不是 src/）
└── src/
    ├── main.js           ← 替换
    ├── router/
    │   └── index.js      ← 新建（原文件未上传，已按 App.vue 路由重建）
    └── views/
        ├── SingleCryptoView.vue    ← 替换（修复 BACKEND_URL）
        └── CombinedCryptoView.vue  ← 替换（修复 BACKEND_URL）

backend/
└── requirements.txt      ← 替换
```

### 无需改动的文件（直接保留原文件）

```
frontend/src/
├── App.vue
├── components/
│   ├── AlgorithmParamsForm.vue
│   ├── AnalysisCharts.vue
│   └── ImageDisplay.vue
backend/
├── app.py
├── config.py
└── core_logic/（全部文件）
```

---

## 二、操作步骤

### 后端

```bash
cd scp-web/backend

# 创建虚拟环境（隔离依赖，避免污染 Homebrew Python）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 验证
python -c "import cv2, numpy, scipy, Crypto, flask; print('✅ 后端依赖正常')"
```

### 前端

```bash
cd scp-web/frontend

# 删除旧的构建工具文件（如果存在）
rm -f vue.config.js babel.config.js .eslintrc.js jsconfig.json

# 安装依赖（Node v25 + Vite 5 完全兼容，无警告）
npm install

# 启动开发服务器
npm run dev
# → 访问 http://localhost:8080
```

### 同时启动（两个终端）

**终端 1（后端）：**
```bash
cd backend && source venv/bin/activate && python app.py
# Flask 运行在 http://127.0.0.1:5000
```

**终端 2（前端）：**
```bash
cd frontend && npm run dev
# Vite 运行在 http://localhost:8080
# /api/* 自动代理到 5000 端口
```

---

## 三、核心变更说明

### 为什么能正常工作

| 旧（Vue CLI）| 新（Vite）|
|---|---|
| `process.env.VUE_APP_BACKEND_URL` | `import.meta.env.VITE_BACKEND_URL ?? ""` |
| `vue.config.js` 配置代理 | `vite.config.js` 配置代理（逻辑相同）|
| `public/index.html` 由 CLI 注入 | `frontend/index.html` 是 Vite 入口 |
| `echarts: ^6.0.0`（不存在的版本）| `echarts: ^5.5.0`（正确版本）|
| Node 18+ 不兼容 Vue CLI | Vite 5 原生支持 Node 25 |

### BACKEND_URL 为空的原因
开发时 `VITE_BACKEND_URL` 未设置，值为 `""`。
这使得 `${BACKEND_URL}/api/upload_image` 变成 `/api/upload_image`，
Vite dev server 的 proxy 规则会将 `/api/*` 转发到 `http://127.0.0.1:5000`。
生产构建后 Flask 直接 serve 前端静态文件，也不需要跨域。

---

## 四、生产部署（可选）

```bash
cd frontend
npm run build
# 产物直接输出到 backend/static/

cd backend
source venv/bin/activate
python app.py
# 访问 http://127.0.0.1:5000 即可，Flask 同时 serve 前后端
```
