<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api } from '../api'
import { loadSession } from '../auth'
import type { Alert } from '../types'

const alerts = ref<Alert[]>([])
const user = loadSession()
const isTourist = computed(() => user?.role === 'tourist')

function alertText(alert: Alert) {
  if (isTourist.value) return alert.audience_messages?.tourist || alert.advice
  return alert.audience_messages?.resident || alert.advice
}

onMounted(async () => {
  alerts.value = (await api.get('/api/alerts')).data
})
</script>

<template>
  <section class="page narrow">
    <div class="page-head">
      <p class="eyebrow">Alerts</p>
      <h1>{{ isTourist ? '游客预警提示' : '预警列表' }}</h1>
      <p class="hint">
        {{ isTourist ? '优先展示适合游客理解和执行的避险文案，重点关注景区、道路、临水临崖和临时集合点。' : '查看当前公开预警和属地避险建议。' }}
      </p>
    </div>
    <RouterLink v-for="alert in alerts" :key="alert.id" :to="`/alerts/${alert.id}`" class="alert-card block-link">
      <span class="level">{{ alert.level }}</span>
      <h2>{{ alert.title }}</h2>
      <small class="role-label">{{ isTourist ? '游客版' : '居民版' }}</small>
      <p>{{ alertText(alert) }}</p>
      <small>{{ alert.data_source_note }}</small>
    </RouterLink>
  </section>
</template>
