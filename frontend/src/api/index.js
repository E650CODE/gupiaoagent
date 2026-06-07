import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

let _disclaimer = '本内容仅为数据分析学习，不构成投资建议'

api.interceptors.response.use(
  (res) => {
    if (res.data && res.data.disclaimer) {
      _disclaimer = res.data.disclaimer
    }
    return res.data
  },
  (err) => {
    const msg = err.response?.data?.msg || err.message || '网络异常'
    return Promise.reject(new Error(msg))
  },
)

export function getDisclaimer() {
  return _disclaimer
}

export default api

// ───── API 方法 ─────
export const health = () => api.get('/health')

export const selectStocks = (body) => api.post('/stock/select', body)
export const predictStock = (body) => api.post('/stock/predict', body)
export const stockDetail = (code) => api.get(`/stock/detail/${code}`)
export const stockStrategies = () => api.get('/stock/strategies')
export const stockList = () => api.get('/stock/list')

export const runBacktest = (body) => api.post('/backtest/run', body)

export const getLLMConfig = () => api.get('/llm/config')
export const updateLLMConfig = (body) => api.put('/llm/config', body)
export const fetchModels = (body) => api.post('/llm/models', body)
export const testLLM = (body) => api.post('/llm/test', body)
export const llmProviders = () => api.get('/llm/providers')