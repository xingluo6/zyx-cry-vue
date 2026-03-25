<template>
  <div id="app">
    <el-container class="app-layout">
      <el-header class="app-header">
        <div class="nav-inner">
          <div class="nav-brand">
            <div class="brand-icon">🔐</div>
            <div class="brand-text">
              <div class="brand-title">图像加密分析平台</div>
              <div class="brand-sub">Image Crypto Analysis</div>
            </div>
          </div>
          <el-menu :default-active="$route.path" mode="horizontal"
            router class="nav-menu" :ellipsis="false">
            <el-menu-item index="/">
              <el-icon><lock /></el-icon>单算法演示
            </el-menu-item>
            <el-menu-item index="/combined">
              <el-icon><connection /></el-icon>组合算法
            </el-menu-item>
            <el-menu-item index="/library">
              <el-icon><folder-opened /></el-icon>图像库
            </el-menu-item>
            <el-menu-item index="/batch">
              <el-icon><files /></el-icon>批量处理
            </el-menu-item>
            <el-menu-item index="/dashboard">
              <el-icon><data-analysis /></el-icon>数据大屏
            </el-menu-item>
            <el-menu-item index="/experiment">
              <el-icon><histogram /></el-icon>实验对比
            </el-menu-item>
          </el-menu>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view v-slot="{ Component, route }">
          <keep-alive :include="['SingleCryptoView','CombinedCryptoView','BatchView','ImageLibraryView']">
            <component :is="Component" :key="route.name" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script>
import { Lock, Connection, FolderOpened, Files, DataAnalysis, Histogram } from '@element-plus/icons-vue'

export default {
  name: 'App',
  components: { Lock, Connection, FolderOpened, Files, DataAnalysis, Histogram },
}
</script>

<style>
html, body, #app { height: 100%; margin: 0; }
.app-layout { min-height: 100vh; display: flex; flex-direction: column; }
.app-header {
  height: 56px !important; padding: 0 !important;
  background: #fff; border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 8px rgba(0,0,0,0.06);
  position: sticky; top: 0; z-index: 100;
}
.nav-inner {
  height: 100%; display: flex; align-items: center;
  padding: 0 24px; gap: 24px;
}
.nav-brand  { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.brand-icon { font-size: 24px; line-height: 1; }
.brand-text { display: flex; flex-direction: column; }
.brand-title { font-size: 15px; font-weight: 700; color: #1a1f36; line-height: 1.2; white-space: nowrap; }
.brand-sub   { font-size: 10px; color: #909399; letter-spacing: 0.5px; line-height: 1.2; }
.nav-menu {
  flex: 1; border-bottom: none !important; height: 56px;
}
.nav-menu .el-menu-item {
  height: 56px !important; line-height: 56px !important;
  font-size: 13px !important; font-weight: 500 !important;
  color: #606266 !important; padding: 0 14px !important;
  display: flex !important; align-items: center !important;
  gap: 4px; border-bottom: 2px solid transparent !important;
  transition: all 0.2s !important;
}
.nav-menu .el-menu-item:hover {
  color: #4f6ef7 !important; background: #f0f2ff !important;
}
.nav-menu .el-menu-item.is-active {
  color: #4f6ef7 !important; border-bottom-color: #4f6ef7 !important;
  background: transparent !important;
}
.app-main {
  flex: 1; padding: 20px 24px !important;
  background: #f0f2f7; overflow-y: auto;
}
</style>