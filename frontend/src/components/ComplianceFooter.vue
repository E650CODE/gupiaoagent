<template>
  <div class="compliance-footer">
    <el-divider />
    <el-alert :title="disclaimer" type="warning" :closable="false" show-icon />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getDisclaimer } from '../api/index.js'

const disclaimer = ref(getDisclaimer())
</script>

<style scoped>
.compliance-footer { margin-top: 20px; }
</style>