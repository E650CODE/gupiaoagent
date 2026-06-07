<template>
  <el-container style="min-height:100vh">
    <!-- 顶栏 -->
    <el-header style="background:#001529;color:#fff;display:flex;align-items:center">
      <el-icon style="font-size:24px;margin-right:10px"><TrendCharts /></el-icon>
      <span style="font-size:18px;font-weight:bold">A股智能选股系统</span>
      <div style="flex:1" />
      <el-menu mode="horizontal" :ellipsis="false" :default-active="route.path"
               background-color="#001529" text-color="#fff" active-text-color="#409eff"
               router style="border:0;display:inline-flex">
        <el-menu-item index="/">
          <el-icon><Search /></el-icon>选股
        </el-menu-item>
        <el-menu-item index="/backtest">
          <el-icon><DataAnalysis /></el-icon>回测
        </el-menu-item>
        <el-menu-item index="/settings/llm" style="margin-left:20px">
          <el-icon><Setting /></el-icon>设置
        </el-menu-item>
      </el-menu>
    </el-header>

    <!-- 主体 -->
    <el-main>
      <router-view />
      <ComplianceFooter />
    </el-main>
  </el-container>
</template>

<script setup>
import { useRoute } from 'vue-router'
import ComplianceFooter from './components/ComplianceFooter.vue'
const route = useRoute()
</script>

<style>
body { margin:0; font-family:'Microsoft YaHei',sans-serif; }
.el-main { max-width:1400px; margin:0 auto; width:100%; }
</style>