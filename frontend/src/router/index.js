import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'HomeSelect',
    component: () => import('../views/HomeSelect.vue'),
  },
  {
    path: '/stock/:code',
    name: 'StockDetail',
    component: () => import('../views/StockDetail.vue'),
    props: true,
  },
  {
    path: '/backtest',
    name: 'BacktestBoard',
    component: () => import('../views/BacktestBoard.vue'),
  },
  {
    path: '/settings/llm',
    name: 'LLMConfig',
    component: () => import('../views/LLMConfig.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})