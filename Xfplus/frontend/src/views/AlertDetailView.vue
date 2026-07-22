<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Mic } from 'lucide-vue-next'
import { api } from '../api'
import { loadSession } from '../auth'
import type { Alert } from '../types'
import { useSpeech } from '../composables/useSpeech'

const route = useRoute()
const alert = ref<Alert | null>(null)
const user = loadSession()
type AudienceRole = 'county_admin' | 'resident' | 'tourist' | 'village_officer' | 'scenic_manager'
const publicAudienceRole = computed<AudienceRole | null>(() => {
  if (user?.role === 'resident' || user?.role === 'tourist') return user.role
  if (user?.role === 'county_admin') return 'county_admin'
  return null
})
const activeRole = ref<AudienceRole>(user?.role === 'county_admin' ? 'county_admin' : user?.role === 'resident' ? 'resident' : 'tourist')
const { speak, activate, message } = useSpeech()
const isTourist = computed(() => user?.role === 'tourist')

const roleLabels: Record<AudienceRole, string> = {
  county_admin: '区县管理版',
  resident: '居民版',
  tourist: '游客版',
  village_officer: '村干部版',
  scenic_manager: '景区管理者版',
}

const visibleRoleLabels = computed(() => {
  if (!publicAudienceRole.value) return roleLabels
  return {
    [publicAudienceRole.value]: roleLabels[publicAudienceRole.value],
  } as Partial<Record<AudienceRole, string>>
})
const currentText = computed(() => alert.value?.audience_messages?.[activeRole.value] || alert.value?.advice || '')

onMounted(async () => {
  alert.value = (await api.get(`/api/alerts/${route.params.id}`)).data
})
</script>

<template>
  <section v-if="alert" class="page narrow">
    <div class="detail-hero">
      <span class="level">{{ alert.level }}</span>
      <h1>{{ alert.title }}</h1>
      <p>{{ alert.duration }} · {{ alert.affected_areas.join('、') }}</p>
      <p v-if="isTourist" class="tourist-detail-note">游客请优先确认所在景区、同行人员和最近出口；无法判断路线时直接联系现场工作人员或使用 SOS。</p>
      <button class="primary-button" @click="speak(currentText)"><Mic :size="18" />播放当前文案</button>
      <button class="ghost-button" @click="activate">🎤 允许语音</button>
      <p v-if="message" class="hint">{{ message }}</p>
    </div>

    <div class="panel alert-guidance-panel">
      <div class="guidance-head">
        <div>
          <h2>避险建议</h2>
          <small>{{ alert.data_source_note }}</small>
        </div>
        <span class="role-label guidance-role">{{ roleLabels[activeRole] }}</span>
      </div>
      <p class="guidance-summary">{{ alert.advice }}</p>
      <div v-if="!publicAudienceRole" class="segmented compact-segmented">
        <button v-for="(_, key) in visibleRoleLabels" :key="key" :class="{ active: activeRole === key }" @click="activeRole = key as AudienceRole">
          {{ roleLabels[key as keyof typeof roleLabels] }}
        </button>
      </div>
      <p class="role-text guidance-text">{{ currentText }}</p>
    </div>
  </section>
</template>
