<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AdminNav from './AdminNav.vue'
import { api } from '../../api'

const stats = ref({ alerts: 0, pushed: 0, broadcasts: 0, incidents: 0, pending: 0 })

onMounted(async () => {
  const [alerts, pushed, broadcasts, incidents] = await Promise.all([
    api.get('/api/alerts'),
    api.get('/api/alerts?is_pushed=true'),
    api.get('/api/broadcasts'),
    api.get('/api/incidents').catch(() => ({ data: { items: [], stats: { pending: 0 } } })),
  ])
  stats.value = {
    alerts: alerts.data.length,
    pushed: pushed.data.length,
    broadcasts: broadcasts.data.length,
    incidents: incidents.data.items.length,
    pending: incidents.data.stats.pending,
  }
})
</script>

<template>
  <section class="admin-page">
    <AdminNav />
    <div class="admin-content">
      <div class="page-head">
        <p class="eyebrow">Admin</p>
        <h1>后台总览</h1>
      </div>
      <div class="metric-grid admin-metrics">
        <div><small>预警事件</small><strong>{{ stats.alerts }}</strong></div>
        <div><small>已模拟推送</small><strong>{{ stats.pushed }}</strong></div>
        <div><small>现场上报</small><strong>{{ stats.incidents }}</strong></div>
        <div><small>待核实事件</small><strong>{{ stats.pending }}</strong></div>
        <div><small>播报记录</small><strong>{{ stats.broadcasts }}</strong></div>
      </div>
    </div>
  </section>
</template>
