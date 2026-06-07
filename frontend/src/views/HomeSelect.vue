<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header><span><el-icon><Monitor /></el-icon> 选股条件</span></template>
      <el-form :inline="true" label-width="80px">
        <el-form-item label="策略">
          <el-checkbox-group v-model="strategies">
            <el-checkbox v-for="s in strategyList" :key="s.key" :label="s.key" :value="s.key">{{ s.name }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="数量">
          <el-select v-model="topN" style="width:100px">
            <el-option v-for="n in [5,10,15,20,30,50]" :key="n" :label="n" :value="n" />
          </el-select>
        </el-form-item>
        <el-form-item label="AI解读">
          <el-switch v-model="enableAI" />
        </el-form-item>
        <el-form-item label="风控过滤">
          <el-switch v-model="enableRisk" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="doSelect">
            <el-icon><Search /></el-icon> 开始选股
          </el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="stockCount" title="合规声明：本结果仅为数据分析学习，不构成投资建议" type="warning" :closable="false" show-icon style="margin-top:8px" />
    </el-card>

    <!-- 结果表格 -->
    <el-card v-if="stocks.length" shadow="never">
      <template #header>结果 (共 {{ stockCount }} 只)</template>
      <el-table :data="stocks" stripe style="width:100%" @row-click="goDetail">
        <el-table-column prop="code" label="代码" width="100" sortable />
        <el-table-column prop="name" label="名称" width="140" />
        <el-table-column prop="close" label="收盘价" width="100" sortable>
          <template #default="{row}">{{ row.close }}</template>
        </el-table-column>
        <el-table-column prop="pct_chg" label="涨幅%" width="90" sortable>
          <template #default="{row}"><span :style="{color:row.pct_chg>=0?'#f56c6c':'#67c23a'}">{{ row.pct_chg }}%</span></template>
        </el-table-column>
        <el-table-column prop="ma5" label="MA5" width="90" />
        <el-table-column prop="ma20" label="MA20" width="90" />
        <el-table-column prop="macd_dif" label="MACD DIF" width="100" sortable />
        <el-table-column prop="rsi6" label="RSI6" width="80" sortable />
        <el-table-column prop="vol_ratio" label="量比" width="80" sortable />
        <el-table-column prop="risk_level" label="风控等级" width="100">
          <template #default="{row}">
            <el-tag :type="row.risk_level==='高'?'danger':row.risk_level==='中'?'warning':'success'" size="small">{{ row.risk_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{row}"><el-button link type="primary" @click.stop="goDetail(row)">详情</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- AI 解读 -->
    <AIReport v-if="aiData" :data="aiData" :loading="aiLoading" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { selectStocks, stockStrategies } from '../api/index.js'
import AIReport from '../components/AIReport.vue'

const router = useRouter()
const strategies = ref(['ma_bull'])
const topN = ref(20)
const enableAI = ref(true)
const enableRisk = ref(true)
const stocks = ref([])
const stockCount = ref(0)
const loading = ref(false)
const aiData = ref(null)
const aiLoading = ref(false)
const strategyList = ref([])

onMounted(async () => {
  try {
    const res = await stockStrategies()
    strategyList.value = res.data || []
  } catch {} // 网络不可用时静默
})

async function doSelect() {
  if (!strategies.value.length) return
  loading.value = true; aiData.value = null
  try {
    const res = await selectStocks({
      strategies: strategies.value,
      top_n: topN.value,
      enable_ai: enableAI.value,
      enable_risk: enableRisk.value,
    })
    const d = res.data
    stocks.value = d.stocks || []
    stockCount.value = d.count || 0
    if (d.ai_explanation) aiData.value = d.ai_explanation
  } catch (e) {
    console.error(e)
  } finally { loading.value = false }
}

function goDetail(row) {
  router.push(`/stock/${row.code}`)
}
</script>