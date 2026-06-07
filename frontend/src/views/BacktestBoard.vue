<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header><el-icon><DataAnalysis /></el-icon> 策略回测</template>
      <el-form :inline="true" label-width="80px">
        <el-form-item label="策略">
          <el-select v-model="strategy" style="width:150px">
            <el-option v-for="s in strategyList" :key="s.key" :label="s.name" :value="s.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始">
          <el-date-picker v-model="start" type="date" value-format="YYYYMMDD" placeholder="20240101" />
        </el-form-item>
        <el-form-item label="结束">
          <el-date-picker v-model="end" type="date" value-format="YYYYMMDD" placeholder="20240601" />
        </el-form-item>
        <el-form-item label="持仓日">
          <el-input-number v-model="holdDays" :min="1" :max="30" style="width:100px" />
        </el-form-item>
        <el-form-item label="资金">
          <el-input-number v-model="initialCash" :min="10000" :max="10000000" :step="100000" style="width:140px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="doBacktest">
            <el-icon><CaretRight /></el-icon> 运行回测
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 指标卡 -->
    <el-row v-if="metrics" :gutter="16" style="margin-bottom:16px">
      <el-col :span="4" v-for="m in metricCards" :key="m.label">
        <el-card shadow="never">
          <div class="metric-label">{{ m.label }}</div>
          <div class="metric-value" :style="{color:m.color}">{{ m.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 净值曲线 -->
    <el-card v-if="navCurve.length" shadow="never" style="margin-bottom:16px">
      <template #header>净值曲线</template>
      <div ref="navChartRef" style="width:100%;height:400px"></div>
    </el-card>

    <!-- 交易明细 -->
    <el-card v-if="trades.length" shadow="never" style="margin-bottom:16px">
      <template #header>交易明细 ({{ trades.length }} 笔)</template>
      <el-table :data="trades" stripe height="300" style="width:100%">
        <el-table-column prop="date" label="日期" width="110" />
        <el-table-column prop="code" label="代码" width="80" />
        <el-table-column prop="action" label="操作" width="70">
          <template #default="{row}"><el-tag :type="row.action==='buy'?'':'danger'" size="small">{{ row.action==='buy'?'买入':'卖出' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="90" />
        <el-table-column prop="qty" label="数量" width="80" />
        <el-table-column prop="pnl" label="盈亏" width="100" sortable>
          <template #default="{row}"><span :style="{color:row.pnl>=0?'#f56c6c':'#67c23a'}">{{ row.pnl }}</span></template>
        </el-table-column>
        <el-table-column prop="return" label="收益率" width="100" sortable>
          <template #default="{row}">{{ (row.return*100).toFixed(2) }}%</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- AI 总结 -->
    <AIReport v-if="aiData" :data="aiData" :loading="aiLoading" />
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { runBacktest, stockStrategies } from '../api/index.js'
import AIReport from '../components/AIReport.vue'

const strategy = ref('ma_bull')
const start = ref('20240101')
const end = ref('20240601')
const holdDays = ref(5)
const initialCash = ref(100000)
const loading = ref(false)
const strategyList = ref([])
const metrics = ref(null)
const navCurve = ref([])
const trades = ref([])
const aiData = ref(null)
const aiLoading = ref(false)
const navChartRef = ref(null)
let navChart = null

const metricCards = ref([])

onMounted(async () => {
  try { const r=await stockStrategies(); strategyList.value=r.data||[] } catch {}
})

async function doBacktest() {
  loading.value = true; aiData.value = null
  try {
    const r = await runBacktest({
      strategy: strategy.value,
      start: start.value, end: end.value,
      params: { initial_cash: initialCash.value, hold_days: holdDays.value, max_positions: 5 },
      enable_ai: true,
    })
    const d = r.data
    metrics.value = d.metrics || {}
    navCurve.value = d.nav_curve || []
    trades.value = d.trades || []
    if (d.ai_summary && !d.ai_summary.error) aiData.value = d.ai_summary
    computeMetrics()
    nextTick(renderNavChart)
  } catch (e) { console.error(e) } finally { loading.value = false }
}

function computeMetrics() {
  if (!metrics.value) return
  const m = metrics.value
  metricCards.value = [
    { label:'累计收益', value:(m.total_return*100).toFixed(2)+'%', color: m.total_return>=0?'#f56c6c':'#67c23a' },
    { label:'年化收益', value:(m.annual_return*100).toFixed(2)+'%', color: m.annual_return>=0?'#f56c6c':'#67c23a' },
    { label:'胜率', value:(m.win_rate*100).toFixed(1)+'%', color:'#409eff' },
    { label:'最大回撤', value:(m.max_drawdown*100).toFixed(2)+'%', color:'#e6a23c' },
    { label:'夏普比率', value:m.sharpe.toFixed(2), color:m.sharpe>=1?'#67c23a':'#909399' },
    { label:'交易次数', value:m.trade_count||0, color:'#909399' },
  ]
}

function renderNavChart() {
  if (!navChartRef.value || !navCurve.value.length) return
  if (!navChart) navChart = echarts.init(navChartRef.value)
  const dates = navCurve.value.map(n => n.date)
  const navs = navCurve.value.map(n => n.nav)
  navChart.setOption({
    tooltip:{trigger:'axis'},
    xAxis:{type:'category',data:dates,axisLabel:{rotate:30,fontSize:10}},
    yAxis:{type:'value',scale:true},
    series:[{
      type:'line',data:navs,areaStyle:{color:'rgba(64,158,255,0.15)'},
      lineStyle:{color:'#409eff',width:2},showSymbol:false,
      markLine:{data:[{type:'average',name:'均值'}]}
    }]
  })
}

watch(()=>navCurve.value.length, ()=>{nextTick(renderNavChart)})
</script>

<style scoped>
.metric-label { font-size:13px; color:#909399; margin-bottom:4px; }
.metric-value { font-size:24px; font-weight:bold; }
</style>