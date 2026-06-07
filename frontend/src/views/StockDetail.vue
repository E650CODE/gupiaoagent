<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header>
        <el-space>
          <el-button @click="$router.back()"><el-icon><ArrowLeft /></el-icon>返回</el-button>
          <strong>{{ code }}</strong>
          <span v-if="name">{{ name }}</span>
        </el-space>
      </template>

      <!-- K 线 -->
      <KLineChart :kline="kline" />
    </el-card>

    <!-- 预测 + 风控 -->
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><el-icon><MagicStick /></el-icon> 趋势预测</template>
          <div v-if="predLoading"><el-icon class="is-loading"><Loading /></el-icon> 预测中...</div>
          <div v-else-if="prediction" class="pred-box">
            <div>方向：<el-tag :type="prediction.direction==='up'?'danger':'success'" size="large">{{ {up:'↑上涨',down:'↓下跌',range:'→震荡'}[prediction.direction]||prediction.direction }}</el-tag></div>
            <div>概率：{{ (prediction.prob*100).toFixed(1) }}%</div>
            <div>置信度：{{ prediction.confidence }}</div>
            <div>区间：{{ prediction.price_low }} ~ {{ prediction.price_high }}</div>
            <div>周期：{{ prediction.horizon_days }} 个交易日</div>
            <el-divider />
            <p>{{ prediction.reasoning }}</p>
            <p v-if="prediction.risk_warning" style="color:#e6a23c">{{ prediction.risk_warning }}</p>
          </div>
          <el-empty v-else description="暂无预测数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><el-icon><WarningFilled /></el-icon> 风险评估</template>
          <div v-if="riskLoading"><el-icon class="is-loading"><Loading /></el-icon> 评估中...</div>
          <div v-else-if="risk" class="risk-box">
            <div>等级：<el-tag :type="risk.risk_level==='高'?'danger':risk.risk_level==='中'?'warning':'success'" size="large">{{ risk.risk_level }}</el-tag></div>
            <div v-if="risk.risk_points?.length">
              <p v-for="p in risk.risk_points" :key="p">• {{ p }}</p>
            </div>
            <div v-if="risk.advice"><el-divider /><p>{{ risk.advice }}</p></div>
            <div v-if="risk.stop_profit || risk.stop_loss" style="margin-top:8px">
              <el-tag v-if="risk.stop_profit" style="margin-right:8px">止盈参考: {{ risk.stop_profit }}</el-tag>
              <el-tag v-if="risk.stop_loss" type="danger">止损参考: {{ risk.stop_loss }}</el-tag>
            </div>
          </div>
          <el-empty v-else description="暂无风控数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- AI 解读 -->
    <AIReport :data="aiData" :loading="false" />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { stockDetail, predictStock } from '../api/index.js'
import KLineChart from '../components/KLineChart.vue'
import AIReport from '../components/AIReport.vue'

const props = defineProps({ code: String })
const kline = ref([])
const name = ref('')
const prediction = ref(null)
const predLoading = ref(false)
const risk = ref(null)
const riskLoading = ref(false)
const aiData = ref(null)

async function load() {
  if (!props.code) return
  try {
    const res = await stockDetail(props.code)
    const d = res.data
    kline.value = d.factors || []
    name.value = ''
  } catch {}
  // 预测
  predLoading.value = true
  try {
    const r = await predictStock({ code: props.code, horizon_days: 5 })
    prediction.value = r.data.prediction || null
    risk.value = r.data.risk || null
    if (prediction.value && !prediction.value.error) {
      aiData.value = {
        reasoning: prediction.value.reasoning,
        risk_warning: prediction.value.risk_warning,
      }
    }
  } catch {} finally { predLoading.value = false }
}
onMounted(load)
watch(()=>props.code, load)
</script>

<style scoped>
.pred-box div, .risk-box div { margin: 6px 0; }
.pred-box p, .risk-box p { margin: 4px 0; line-height: 1.6; }
</style>