<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Bell, Footprints, MapPin, Mic, RefreshCw, ShieldCheck } from 'lucide-vue-next'
import { api } from '../api'
import { loadSession } from '../auth'
import type { Alert, DispatchMessage, RiskPoint } from '../types'
import { useSpeech } from '../composables/useSpeech'

const alerts = ref<Alert[]>([])
const pushedAlert = ref<Alert | null>(null)
const weather = ref<any>(null)
const riskPoints = ref<RiskPoint[]>([])
const messages = ref<DispatchMessage[]>([])
const user = loadSession()
const { speak, stop, activate, status } = useSpeech()
const latestAlertBroadcasting = ref(false)
let timer: number | undefined

const topRisk = computed(() => riskPoints.value.find((item) => item.risk_level === '高') || riskPoints.value[0])
const topMessage = computed(() => messages.value[0])
const latestAlert = computed(() => pushedAlert.value || alerts.value[0])
const audienceRole = computed<'resident' | 'tourist'>(() => (user?.role === 'tourist' ? 'tourist' : 'resident'))
const isTourist = computed(() => audienceRole.value === 'tourist')
const audienceLabel = computed(() => (audienceRole.value === 'tourist' ? '游客提示' : '居民提示'))
const heroTitle = computed(() => (isTourist.value ? '张家界游客应急平台' : '张家界·智瞳应急平台'))
const heroSubtitle = computed(() =>
  isTourist.value ? '面向景区游览、临时避险、路线求助和游客通知' : '守护世界遗产地，AI 让应急更及时',
)
const heroEyebrow = computed(() =>
  isTourist.value ? '景区预警 · 游客求助 · 临时避险' : '预警动态 · 站内消息 · 安置指引',
)
const riskTitle = computed(() => (isTourist.value ? '景区风险提醒' : '中高风险点'))
const messagePrefix = computed(() => (isTourist.value ? '游客通知' : '上级调度'))
const touristActionCards = computed(() => [
  {
    title: '确认所在景区',
    text: user?.district ? `当前按 ${user.district} 接收属地提醒` : '未绑定区县时默认接收全市公开预警',
  },
  {
    title: '优先离开临水临崖区域',
    text: topRisk.value?.action || '暴雨、落石、积水时听从景区工作人员指引',
  },
  {
    title: '无法判断位置时直接 SOS',
    text: '游客上报会自动标记为待核验，SOS 会按最高优先级进入工作台',
  },
])
const visibleRiskPoints = computed(() => {
  if (!isTourist.value) return riskPoints.value.slice(0, 2)
  const scenicPoints = riskPoints.value.filter((item) => item.scenic_area || item.name.includes('景区'))
  return (scenicPoints.length ? scenicPoints : riskPoints.value).slice(0, 3)
})

function alertAudienceText(alert: Alert) {
  return alert.audience_messages?.[audienceRole.value] || alert.advice || alert.title
}

async function load() {
  const [alertsRes, pushedRes, riskRes, inboxRes] = await Promise.all([
    api.get('/api/alerts?limit=3'),
    api.get('/api/alerts?is_pushed=true&limit=1'),
    api.get('/api/risk/current'),
    api.get('/api/messages/inbox').catch(() => ({ data: [] })),
  ])
  alerts.value = alertsRes.data
  pushedAlert.value = pushedRes.data[0] || null
  weather.value = riskRes.data.weather
  riskPoints.value = riskRes.data.points
  messages.value = inboxRes.data
}

watch(status, (value) => {
  if (value === 'speaking') {
    latestAlertBroadcasting.value = true
    return
  }
  if (value === 'needs_user_activation') {
    window.setTimeout(() => {
      if (status.value === 'needs_user_activation') {
        latestAlertBroadcasting.value = false
      }
    }, 500)
    return
  }
  if (value === 'idle' || value === 'unsupported_or_blocked') {
    latestAlertBroadcasting.value = false
  }
})

function toggleLatestAlertSpeech() {
  if (latestAlertBroadcasting.value) {
    stop()
    latestAlertBroadcasting.value = false
    return
  }
  const alert = latestAlert.value
  if (!alert) return
  latestAlertBroadcasting.value = true
  speak(alertAudienceText(alert))
}

onMounted(() => {
  load()
  timer = window.setInterval(load, 30000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
  stop()
})
</script>

<template>
  <div class="resident-home" :class="{ 'tourist-home': isTourist }">
  <section class="hero-band">
    <div class="hero-copy">
      <p class="eyebrow">{{ heroEyebrow }}</p>
      <h1>{{ heroTitle }}</h1>
      <p class="subtitle">{{ heroSubtitle }}</p>
      <div class="card-actions">
        <button @click="toggleLatestAlertSpeech">
          <Mic :size="16" />
          {{ latestAlertBroadcasting ? '关闭语音播报' : '语音播报最新预警' }}
        </button>
        <button class="ghost-button" @click="activate">🎤 允许语音</button>
      </div>
    </div>
    <div class="risk-console">
      <span class="console-label">{{ isTourist ? '当前游览风险' : '当前综合风险' }}</span>
      <strong>{{ topRisk?.risk_level || '待观察' }}</strong>
      <p>{{ weather?.summary || '正在获取张家界天气与风险数据' }}</p>
      <small>24h 降雨量：{{ weather?.rainfall_24h ?? '--' }} mm · {{ weather?.source }}</small>
    </div>
  </section>

  <RouterLink v-if="topMessage" to="/messages" class="push-banner">
    <Bell :size="18" />
    <span>{{ messagePrefix }}：{{ topMessage.title }} · {{ topMessage.content }}</span>
  </RouterLink>

  <RouterLink v-if="pushedAlert && (!isTourist || !topMessage)" :to="`/alerts/${pushedAlert.id}`" class="push-banner">
    <Bell :size="18" />
    <span>最新预警：{{ pushedAlert.title }}，点击查看详情</span>
  </RouterLink>

  <section v-if="isTourist" class="tourist-quick-grid">
    <article v-for="card in touristActionCards" :key="card.title" class="tourist-quick-card">
      <MapPin v-if="card.title.includes('景区')" :size="20" />
      <Footprints v-else-if="card.title.includes('离开')" :size="20" />
      <Bell v-else :size="20" />
      <strong>{{ card.title }}</strong>
      <span>{{ card.text }}</span>
    </article>
  </section>

  <section class="content-grid">
    <article class="panel latest-alert">
      <div class="section-head">
        <div>
          <p class="eyebrow">Latest Alert</p>
          <h2>{{ isTourist ? '游客版预警' : '最新预警' }}</h2>
        </div>
        <button class="icon-button" @click="load" title="刷新"><RefreshCw :size="18" /></button>
      </div>
      <div v-for="alert in alerts.slice(0, 1)" :key="alert.id" class="alert-card">
        <span class="level">{{ alert.level }}</span>
        <h3>{{ alert.title }}</h3>
        <small class="role-label">{{ audienceLabel }}</small>
        <p>{{ alertAudienceText(alert) }}</p>
        <div class="card-actions">
          <RouterLink :to="`/alerts/${alert.id}`" class="text-link">查看详情</RouterLink>
          <button @click="speak(alertAudienceText(alert))"><Mic :size="16" />播放</button>
        </div>
      </div>
    </article>

    <article class="panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Risk Points</p>
          <h2>{{ riskTitle }}</h2>
        </div>
        <ShieldCheck :size="22" />
      </div>
      <div v-for="point in visibleRiskPoints" :key="point.id" class="risk-row">
        <span :class="['dot', point.warning_color]" />
        <div>
          <strong>{{ point.name }}</strong>
          <small>{{ isTourist && point.scenic_area ? `${point.scenic_area} · ${point.action}` : point.action }}</small>
        </div>
        <span>{{ point.risk_score }}</span>
      </div>
      <RouterLink to="/risk-map" class="primary-button wide">{{ isTourist ? '查看景区风险地图' : '打开风险地图' }}</RouterLink>
    </article>
  </section>
  </div>
</template>
