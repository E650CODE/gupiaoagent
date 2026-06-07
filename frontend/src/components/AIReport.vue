<template>
  <el-card shadow="never" style="margin-bottom:16px">
    <template #header>
      <span><el-icon><MagicStick /></el-icon> AI 智能分析</span>
    </template>
    <div v-if="loading" style="text-align:center;padding:20px">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <p>AI 正在分析中...</p>
    </div>
    <el-empty v-else-if="!data" description="暂无数据" />
    <div v-else-if="data.error" class="ai-error">
      <el-alert :title="'AI 分析暂不可用: '+data.error" type="warning" :closable="false" />
    </div>
    <div v-else class="ai-content">
      <p v-if="data.logic"><strong>核心逻辑：</strong>{{ data.logic }}</p>
      <p v-if="data.summary"><strong>总结：</strong>{{ data.summary }}</p>
      <p v-if="data.sector_hot"><strong>板块热度：</strong>{{ data.sector_hot }}</p>
      <p v-if="data.reasoning"><strong>走势分析：</strong>{{ data.reasoning }}</p>
      <p v-if="data.risk_warning" style="color:#e6a23c"><strong>风险提示：</strong>{{ data.risk_warning }}</p>
      <div v-if="data.common_features && data.common_features.length">
        <strong>共性特征：</strong>
        <el-tag v-for="f in data.common_features" :key="f" style="margin-right:6px;margin-bottom:4px">{{ f }}</el-tag>
      </div>
      <div v-if="data.pros && data.pros.length">
        <strong>优点：</strong>
        <ul><li v-for="p in data.pros" :key="p">{{ p }}</li></ul>
      </div>
      <div v-if="data.cons && data.cons.length">
        <strong>不足：</strong>
        <ul><li v-for="c in data.cons" :key="c">{{ c }}</li></ul>
      </div>
      <div v-if="data.optimize && data.optimize.length">
        <strong>优化建议：</strong>
        <ul><li v-for="o in data.optimize" :key="o">{{ o }}</li></ul>
      </div>
    </div>
  </el-card>
</template>
<script setup>
defineProps({ data: { type: Object, default: null }, loading: { type: Boolean, default: false } })
</script>
<style scoped>
.ai-content p { margin: 8px 0; line-height: 1.7; }
.ai-error { padding: 12px 0; }
</style>