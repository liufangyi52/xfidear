<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { MapPin, Siren } from 'lucide-vue-next'
import { api } from '../api'
import { loadSession } from '../auth'
import type { Incident, IncidentType } from '../types'

const DRAFT_KEY = 'zjj_incident_draft'
const user = loadSession()
const isTourist = user?.role === 'tourist'
const incidents = ref<Incident[]>([])
const notice = ref('')
const isSubmitting = ref(false)
const hasDraft = ref(false)
const form = ref({
  type: 'other' as IncidentType,
  description: isTourist
    ? '我在景区游览时发现道路积水或人员滞留，请求现场核实和路线指引。'
    : '金鞭溪水位上涨，有游客滞留，请求现场核实。',
  district: user?.district || '',
  scenic_area: isTourist ? '张家界核心景区' : '',
  lat: 29.3472,
  lng: 110.5587,
})

const reportTitle = isTourist ? '游客求助 / SOS' : '现场上报 / SOS 求助'
const reportHint = isTourist
  ? '用于游客在景区遇到迷路、滞留、受伤、道路中断或需要临时避险时快速求助。普通上报会进入待核验，SOS 会按最高优先级进入指挥处置。'
  : '居民和游客可在这里提交现场情况。SOS 会作为最高优先级事件进入指挥处置。'
const recentTitle = isTourist ? '游客可见求助记录' : '最近可见事件'

const visibleIncidents = computed(() =>
  [...incidents.value].sort((left, right) => (right.created_at || '').localeCompare(left.created_at || '')),
)

async function loadIncidents() {
  const { data } = await api.get('/api/incidents').catch(() => ({ data: { items: [] } }))
  incidents.value = data.items || []
}

function saveDraft() {
  localStorage.setItem(DRAFT_KEY, JSON.stringify(form.value))
  hasDraft.value = true
}

function restoreDraft() {
  const raw = localStorage.getItem(DRAFT_KEY)
  if (!raw) return
  form.value = { ...form.value, ...JSON.parse(raw) }
  hasDraft.value = true
  notice.value = '已恢复离线草稿，确认位置后可继续提交。'
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY)
  hasDraft.value = false
}

function locate() {
  if (!navigator.geolocation) {
    notice.value = '当前浏览器不支持定位，可手动填写经纬度或使用默认景区坐标。'
    return
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      form.value.lat = Number(pos.coords.latitude.toFixed(6))
      form.value.lng = Number(pos.coords.longitude.toFixed(6))
      notice.value = '已获取当前位置，可直接提交现场上报。'
    },
    () => {
      notice.value = '定位未授权，请手动填写经纬度；当前已保留张家界核心景区演示坐标。'
    },
    { enableHighAccuracy: true, timeout: 6000 },
  )
}

async function submitIncident(isSos = false) {
  const payload = {
    ...form.value,
    type: isSos ? 'sos' : form.value.type,
    description: isSos ? `SOS 一键求助：${form.value.description}` : form.value.description,
    district: form.value.district || user?.district || undefined,
    scenic_area: form.value.scenic_area || undefined,
  }
  if (!navigator.onLine) {
    saveDraft()
    notice.value = '当前网络不可用，已保存离线草稿，恢复网络后可继续提交。'
    return
  }
  isSubmitting.value = true
  notice.value = '处理中，请稍候...'
  try {
    const { data } = await api.post('/api/incidents', payload)
    incidents.value = [data, ...incidents.value]
    clearDraft()
    notice.value = isSos
      ? 'SOS 已提交，工作台会以最高优先级看到该事件。'
      : isTourist
        ? '游客上报已提交，系统已标记为需管理员审核。'
        : '现场事件已提交，风险地图和工作台地图区域将同步显示。'
  } catch (error: any) {
    saveDraft()
    notice.value = error?.response?.data?.detail || '提交失败，已保存草稿，请稍后重试。'
  } finally {
    isSubmitting.value = false
  }
}

function handleOnline() {
  if (localStorage.getItem(DRAFT_KEY)) {
    hasDraft.value = true
    notice.value = '网络已恢复，存在离线草稿，可点击“恢复草稿”继续提交。'
  }
}

onMounted(() => {
  loadIncidents()
  hasDraft.value = !!localStorage.getItem(DRAFT_KEY)
  window.addEventListener('online', handleOnline)
})
</script>

<template>
  <section class="page report-sos-page">
    <article class="panel incident-report-panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Field Report / SOS</p>
          <h1>{{ reportTitle }}</h1>
          <p class="hint">{{ reportHint }}</p>
        </div>
        <Siren :size="28" />
      </div>
      <p v-if="isTourist" class="notice">游客端不要求绑定社区；请尽量填写景区/地标、同行人数和可见指示牌。上报会标记为“需管理员审核”。</p>
      <div class="incident-form">
        <label>事件类型
          <select v-model="form.type">
            <option value="other">自动识别</option>
            <option value="flood">积水/山洪</option>
            <option value="landslide">滑坡/落石</option>
            <option value="road">道路中断</option>
            <option value="medical">人员受伤</option>
            <option value="shelter">安置需求</option>
          </select>
        </label>
        <label>事件描述
          <textarea
            v-model="form.description"
            :placeholder="isTourist ? '例如：我在天门山索道出口附近，同行 2 人，前方道路积水无法通过' : '例如：金鞭溪水位上涨，有游客滞留'"
          />
        </label>
        <div class="form-row">
          <label>{{ isTourist ? '所在区县' : '区县' }}<input v-model="form.district" placeholder="可选，系统可自动推断" /></label>
          <label>{{ isTourist ? '景区/地标/入口' : '景区/地点' }}<input v-model="form.scenic_area" placeholder="如天门山索道、金鞭溪、武陵源入口" /></label>
        </div>
        <div class="form-row">
          <label>纬度<input v-model.number="form.lat" /></label>
          <label>经度<input v-model.number="form.lng" /></label>
        </div>
        <div class="card-actions">
          <button class="ghost-button" @click="locate"><MapPin :size="16" />自动定位</button>
          <button v-if="hasDraft" class="ghost-button" @click="restoreDraft">恢复草稿</button>
          <button :disabled="isSubmitting" @click="submitIncident(false)">{{ isSubmitting ? '处理中...' : isTourist ? '提交游客求助' : '提交上报' }}</button>
          <button class="danger-button" :disabled="isSubmitting" @click="submitIncident(true)">SOS 一键求助</button>
        </div>
        <p v-if="notice" class="notice">{{ notice }}</p>
      </div>
    </article>

    <article class="panel recent-incidents-panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">My Reports</p>
          <h2>{{ recentTitle }}</h2>
        </div>
      </div>
      <div class="recent-incidents-list">
        <div v-for="incident in visibleIncidents" :key="incident.id" class="incident-chip">
        <strong>{{ incident.scenic_area || incident.district }} · {{ incident.type }} · {{ incident.status }}</strong>
          <span>{{ incident.description }}</span>
          <small>{{ incident.created_at }}</small>
        </div>
      </div>
    </article>
  </section>
</template>
