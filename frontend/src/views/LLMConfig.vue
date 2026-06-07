<template>
  <div>
    <el-card shadow="never" style="margin-bottom:16px">
      <template #header><el-icon><Setting /></el-icon> 大模型 API 配置</template>
      <p style="color:#909399;font-size:13px">每个 Agent 可独立配置不同的模型和参数。配置仅保存在本地，API Key 加密存储。</p>
    </el-card>

    <el-table :data="agents" stripe style="width:100%">
      <el-table-column label="Agent" width="120">
        <template #default="{row}">{{ AGENT_LABELS[row.agent]||row.agent }}</template>
      </el-table-column>

      <el-table-column label="Provider" width="150">
        <template #default="{row}">
          <el-select v-model="row.config.provider" @change="(v)=>onProviderChange(row,v)">
            <el-option v-for="p in providers" :key="p.key" :label="p.name" :value="p.key" />
          </el-select>
        </template>
      </el-table-column>

      <el-table-column label="接口地址 (base_url)" min-width="240">
        <template #default="{row}">
          <el-input v-model="row.config.base_url" placeholder="自动填充或手动输入" />
        </template>
      </el-table-column>

      <el-table-column label="API Key" min-width="200">
        <template #default="{row}">
          <el-input v-model="row.config.api_key" :type="showKey[row.agent]?'text':'password'" placeholder="输入 API Key">
            <template #suffix>
              <el-icon style="cursor:pointer" @click="toggleKey(row.agent)">
                <View v-if="showKey[row.agent]" /><Hide v-else />
              </el-icon>
            </template>
          </el-input>
        </template>
      </el-table-column>

      <el-table-column label="模型" min-width="160">
        <template #default="{row}">
          <el-space>
            <el-select v-model="row.config.model" filterable allow-create style="width:120px">
              <el-option v-for="m in row.models" :key="m" :label="m" :value="m" />
            </el-select>
            <el-button size="small" :loading="row.loadingModels" @click="loadModels(row)">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </el-space>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="160">
        <template #default="{row}">
          <el-space>
            <el-button size="small" type="primary" :loading="row.saving" @click="saveConfig(row)">保存</el-button>
            <el-button size="small" :loading="row.testing" @click="testConfig(row)">测试</el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>

    <!-- 测试结果 -->
    <el-dialog v-model="testDialog" title="连通性测试" width="400">
      <div v-if="testResult">
        <el-alert v-if="testResult.ok" title="连接成功" type="success" :closable="false" show-icon />
        <el-alert v-else title="连接失败" type="error" :closable="false" show-icon />
        <p>延迟: {{ testResult.latency_ms }}ms</p>
        <p v-if="testResult.sample">响应: {{ testResult.sample }}</p>
        <p v-if="testResult.error">错误: {{ testResult.error }}</p>
      </div>
    </el-dialog>

    <ComplianceFooter />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getLLMConfig, updateLLMConfig, fetchModels, testLLM, llmProviders } from '../api/index.js'
import ComplianceFooter from '../components/ComplianceFooter.vue'

const AGENT_LABELS = { selector:'选股', predictor:'预测', risk:'风控', backtest:'回测' }
const AGENT_KEYS = ['selector','predictor','risk','backtest']
const agents = reactive([])
const providers = ref([])
const showKey = reactive({})
const testDialog = ref(false)
const testResult = ref(null)

onMounted(load)

async function load() {
  try {
    const [cfg, prov] = await Promise.all([getLLMConfig(), llmProviders()])
    providers.value = Object.entries(prov.data||{}).map(([k,v])=>({key:k,...v}))
    agents.splice(0, agents.length, ...AGENT_KEYS.map(k => ({
      agent: k,
      config: cfg.data?.agents?.[k] || { provider:'deepseek',base_url:'',api_key:'',model:'' },
      models: [],
      loadingModels: false,
      saving: false,
      testing: false,
    })))
  } catch {}
}

function onProviderChange(row, key) {
  const p = providers.value.find(x => x.key === key)
  if (p && p.base_url) row.config.base_url = p.base_url
}

function toggleKey(agent) { showKey[agent] = !showKey[agent] }

async function loadModels(row) {
  row.loadingModels = true
  try {
    const r = await fetchModels({ provider: row.config.provider, base_url: row.config.base_url, api_key: row.config.api_key })
    row.models = r.data?.models || []
  } catch (e) { row.models = []; console.error(e) }
  finally { row.loadingModels = false }
}

async function saveConfig(row) {
  row.saving = true
  try {
    await updateLLMConfig({ agent: row.agent, config: row.config })
  } catch (e) { console.error(e) }
  finally { row.saving = false }
}

async function testConfig(row) {
  row.testing = true
  try {
    const r = await testLLM({ provider: row.config.provider, base_url: row.config.base_url, api_key: row.config.api_key, model: row.config.model })
    testResult.value = r.data
    testDialog.value = true
  } catch (e) { console.error(e) }
  finally { row.testing = false }
}
</script>