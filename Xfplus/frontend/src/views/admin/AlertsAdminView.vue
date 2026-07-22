<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import WorkbenchBackButton from '../../components/WorkbenchBackButton.vue'
import { api } from '../../api'
import { loadSession } from '../../auth'
import type { Alert } from '../../types'

const alerts = ref<Alert[]>([])
const notice = ref('')
const generatingText = ref(false)
let noticeTimer: number | undefined
const user = loadSession()
const canCreateAlert = computed(() => user?.role === 'city_admin' || user?.role === 'county_admin')
type AudienceDraftKey = 'county_admin' | 'village_officer' | 'resident' | 'tourist' | 'scenic_manager'
const allAudienceDrafts: Array<{ key: AudienceDraftKey; label: string; hint: string }> = [
  { key: 'county_admin', label: '区县管理', hint: '会商、调度、督办' },
  { key: 'resident', label: '居民', hint: '避险、转移、安置' },
  { key: 'tourist', label: '游客', hint: '停游、疏导、求助' },
]
const audienceDrafts = computed(() =>
  user?.role === 'city_admin'
    ? allAudienceDrafts.filter((draft) => draft.key === 'county_admin')
    : allAudienceDrafts.filter((draft) => draft.key === 'resident' || draft.key === 'tourist'),
)
const audienceHint = computed(() =>
  user?.role === 'city_admin'
    ? '市级只下发给对应区县级应急管理人员'
    : '区县级只推送给本区县居民和游客',
)
const alertLevels = [
  { value: '红色', label: 'Ⅰ 级 / 红色' },
  { value: '橙色', label: 'Ⅱ 级 / 橙色' },
  { value: '黄色', label: 'Ⅲ 级 / 黄色' },
  { value: '蓝色', label: 'Ⅳ 级 / 蓝色' },
]
const nationalDurationOptions: Record<string, { value: string; label: string }[]> = {
  红色: [
    { value: '未来 30 分钟', label: '未来 30 分钟 / 立即处置' },
    { value: '未来 1 小时', label: '未来 1 小时 / 立即响应' },
    { value: '未来 2 小时', label: '未来 2 小时 / 高压管控' },
    { value: '未来 3 小时', label: '未来 3 小时 / 持续处置' },
  ],
  橙色: [
    { value: '未来 1 小时', label: '未来 1 小时 / 快速响应' },
    { value: '未来 3 小时', label: '未来 3 小时 / 重点管控' },
    { value: '未来 6 小时', label: '未来 6 小时 / 连续巡查' },
    { value: '未来 12 小时', label: '未来 12 小时 / 延伸防控' },
  ],
  黄色: [
    { value: '未来 3 小时', label: '未来 3 小时 / 加密巡查' },
    { value: '未来 6 小时', label: '未来 6 小时 / 加强巡查' },
    { value: '未来 12 小时', label: '未来 12 小时 / 持续关注' },
    { value: '未来 24 小时', label: '未来 24 小时 / 常态值守' },
  ],
  蓝色: [
    { value: '未来 6 小时', label: '未来 6 小时 / 关注变化' },
    { value: '未来 12 小时', label: '未来 12 小时 / 持续关注' },
    { value: '未来 24 小时', label: '未来 24 小时 / 提醒防范' },
    { value: '未来 48 小时', label: '未来 48 小时 / 趋势观察' },
  ],
}
const form = reactive({
  title: '大峡谷强降雨诱发滑坡风险预警',
  disaster_type: '暴雨/山洪/滑坡',
  level: '橙色',
  affected_areas: '张家界大峡谷,玻璃桥入口道路',
  started_at: '2026-05-28 14:00',
  duration: '未来 3 小时',
  advice: '暂停峡谷涉水游览，游客向大峡谷游客服务中心有序转移。',
  status: 'active',
  data_source_note: '基于张家界山区景区强降雨风险场景模拟',
  audience_messages: {
    county_admin: '',
    resident: '',
    tourist: '',
    village_officer: '',
    scenic_manager: '',
  },
})
const levelTone = computed(() => `level-${form.level}`)
const durationOptions = computed(() => nationalDurationOptions[form.level] || nationalDurationOptions.蓝色)

watch(
  () => form.level,
  () => {
    form.duration = durationOptions.value[0]?.value || form.duration
  },
)

function showNotice(message: string) {
  notice.value = message
  if (noticeTimer) {
    window.clearTimeout(noticeTimer)
  }
  noticeTimer = window.setTimeout(() => {
    notice.value = ''
    noticeTimer = undefined
  }, 5000)
}

async function load() {
  alerts.value = (await api.get('/api/alerts')).data
}

function payload() {
  const audience_messages = {
    county_admin: '',
    resident: '',
    tourist: '',
    village_officer: '',
    scenic_manager: '',
  }
  audienceDrafts.value.forEach((draft) => {
    audience_messages[draft.key] = form.audience_messages[draft.key]
  })
  return {
    ...form,
    audience_messages,
    affected_areas: form.affected_areas.split(',').map((item) => item.trim()).filter(Boolean),
  }
}

async function generateText() {
  if (generatingText.value) return
  generatingText.value = true
  const startedAt = performance.now()
  showNotice('AI 正在读取实时风险、事件和安置点数据，生成应急方案中...')
  try {
    const { data } = await api.post('/api/generate_alert_text', payload())
    audienceDrafts.value.forEach((draft) => {
      form.audience_messages[draft.key] = data.messages[draft.key] || ''
    })
    const seconds = Math.max(1, Math.round((performance.now() - startedAt) / 1000))
    showNotice(data.fallback_used
      ? `已生成，用时约 ${seconds} 秒。当前 AI 使用备用模式（${data.llm_provider}），回答质量可能有波动`
      : `AI 文案已生成，用时约 ${seconds} 秒，当前使用 ${data.llm_provider}`)
  } catch (error: any) {
    showNotice(error?.response?.data?.detail || 'AI 文案生成失败，请稍后重试。')
  } finally {
    generatingText.value = false
  }
}

async function createAlert() {
  if (!canCreateAlert.value) {
    showNotice('社区/村部干部不可创建新预警，只能转发上级预警。')
    return
  }
  await api.post('/api/alerts', payload())
  showNotice('预警已保存')
  await load()
}

async function pushAlert(alert: Alert) {
  await api.post(`/api/alerts/${alert.id}/push`)
  showNotice(user?.role === 'city_admin'
    ? '已下发对应区县级应急管理人员'
    : '已推送到本区县居民和游客账号')
  await load()
}

async function unpushAlert(alert: Alert) {
  await api.post(`/api/alerts/${alert.id}/unpush`)
  showNotice('已取消推送，前台首页将不再展示该预警横幅')
  await load()
}

async function forwardAlert(alert: Alert) {
  await api.post(`/api/alerts/${alert.id}/forward`)
  showNotice('已转发上级预警，本辖区居民和游客将收到站内消息')
}

onMounted(async () => {
  await load()
})

onUnmounted(() => {
  if (noticeTimer) {
    window.clearTimeout(noticeTimer)
  }
})
</script>

<template>
  <section class="admin-page admin-page-full">
    <div class="admin-content">
      <div class="work-page-titlebar">
        <h1>{{ canCreateAlert ? '预警发布' : '预警转发' }}</h1>
        <WorkbenchBackButton />
      </div>
      <p v-if="notice" class="notice">{{ notice }}</p>
      <div class="admin-split alert-admin-split">
        <form class="panel form-panel alert-form-panel" @submit.prevent="createAlert">
          <p v-if="!canCreateAlert" class="hint">当前社区/村部角色只允许转发上级预警，不可创建新的全市或区县预警。</p>
          <label class="wide-field">标题<input v-model="form.title" :disabled="!canCreateAlert" /></label>
          <label>等级
            <select v-model="form.level" :class="['alert-level-select', levelTone]" :disabled="!canCreateAlert">
              <option v-for="level in alertLevels" :key="level.value" :value="level.value">{{ level.label }}</option>
            </select>
          </label>
          <label>持续时间
            <select v-model="form.duration" class="alert-duration-select" :disabled="!canCreateAlert">
              <option v-for="duration in durationOptions" :key="duration.value" :value="duration.value">{{ duration.label }}</option>
            </select>
          </label>
          <label class="wide-field">影响区域<input v-model="form.affected_areas" :disabled="!canCreateAlert" /></label>
          <label class="wide-field">避险建议<textarea v-model="form.advice" :disabled="!canCreateAlert" /></label>
          <fieldset class="wide-field audience-draft-field" :class="{ single: audienceDrafts.length === 1 }">
            <legend>
              预警文案
              <small>{{ audienceHint }}</small>
            </legend>
            <label v-for="draft in audienceDrafts" :key="draft.key" class="audience-draft-card">
              <span>{{ draft.label }}<small>{{ draft.hint }}</small></span>
              <textarea
                v-model="form.audience_messages[draft.key]"
                class="audience-draft"
                :disabled="!canCreateAlert"
                :placeholder="`请输入或生成面向${draft.label}的预警文案`"
              />
            </label>
          </fieldset>
          <div class="form-actions">
            <button type="button" class="ghost-button ai-generate-button" :disabled="!canCreateAlert || generatingText" @click="generateText">
              <span v-if="generatingText" class="button-spinner" aria-hidden="true"></span>
              {{ generatingText ? '生成方案中...' : 'AI 生成文案' }}
            </button>
            <button class="primary-button" :disabled="!canCreateAlert || generatingText">保存预警</button>
          </div>
          <p v-if="generatingText" class="hint ai-generate-hint">正在结合实时天气、风险点、现场事件和安置点容量生成，请稍候。</p>
        </form>

        <div class="panel table-panel">
          <div v-for="alert in alerts" :key="alert.id" class="admin-row alert-admin-row">
            <div>
              <strong>{{ alert.title }}</strong>
              <small>{{ alert.level }} · {{ alert.is_pushed ? '已推送' : '未推送' }}</small>
            </div>
            <div class="alert-row-actions">
              <button v-if="canCreateAlert" @click="pushAlert(alert)">推送</button>
              <button v-if="canCreateAlert && alert.is_pushed" class="ghost-button" @click="unpushAlert(alert)">取消推送</button>
              <button v-if="!canCreateAlert" @click="forwardAlert(alert)">转发预警</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
