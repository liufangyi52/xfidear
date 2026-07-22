<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import WorkbenchBackButton from '../components/WorkbenchBackButton.vue'
import { api } from '../api'
import { loadSession } from '../auth'
import type { DispatchMessage, Role } from '../types'

const route = useRoute()
const user = loadSession()
const messages = ref<DispatchMessage[]>([])
const sendNotice = ref('')
const inboxNotice = ref('')
const sending = ref(false)
const suggestionSending = ref(false)
const activeSuggestionId = ref<number | null>(null)
const lastSentMessage = ref<DispatchMessage | null>(null)
const selectedSuggestionId = ref<number | null>(null)
const activeCityInboxSection = ref<'suggestions' | 'history' | 'reply' | 'forward'>('suggestions')
const activeInboxStatus = ref<'all' | 'pending_review' | 'replied' | 'forwarded' | 'closed'>('all')
const suggestionFiles = ref<File[]>([])

const isAdmin = computed(() => !!user?.role?.includes('admin'))
const isCityAdmin = computed(() => user?.role === 'city_admin')
const isInboxAdmin = computed(() => user?.role === 'city_admin' || user?.role === 'county_admin')
const isPublicUser = computed(() => user?.role === 'resident' || user?.role === 'tourist')
const isEmbedded = computed(() => route.query.embedded === '1' && window.parent !== window)
const preserveStandaloneSplitLayout = computed(() => isInboxAdmin.value && !isEmbedded.value)
const visibleInbox = computed(() => {
  if (isInboxAdmin.value) return messages.value
  return messages.value.filter((message) => message.source_type !== 'public_suggestion' || message.sender_id === user?.id)
})
const publicSuggestions = computed(() => messages.value.filter((message) => message.source_type === 'public_suggestion'))

const targets = ref<Role[]>(
  user?.role === 'city_admin'
    ? ['county_admin', 'community_admin', 'resident', 'tourist']
    : ['community_admin', 'resident', 'tourist'],
)
const form = reactive({
  title: '应急调度通知',
  content: '请关注最新预警信息，远离临崖、临水和低洼区域，服从现场工作人员指引。',
})
const suggestionForm = reactive({
  title: '现场信息建议',
  content: '',
  district: user?.district || '武陵源区',
  community: user?.community || '',
})
const reviewDrafts = reactive<Record<number, { reply: string; note: string; status: string; forwardTitle: string; forwardContent: string; roles: Role[] }>>({})

const allowedTargets = computed<Role[]>(() => {
  if (user?.role === 'city_admin') return ['county_admin', 'community_admin', 'resident', 'tourist']
  if (user?.role === 'county_admin') return ['community_admin', 'resident', 'tourist']
  if (user?.role === 'community_admin') return ['community_admin', 'resident', 'tourist']
  return []
})

const roleLabels: Record<Role, string> = {
  city_admin: '市级部门',
  county_admin: '区县级部门',
  community_admin: '社区/村干部',
  resident: '居民',
  tourist: '游客',
}

const statusLabels: Record<string, string> = {
  sent: '已发送',
  pending_review: '待审核',
  replied: '已回复',
  closed: '已办结',
  forwarded: '已转派',
}

const targetSummary = computed(() => targets.value.map((role) => roleLabels[role]).join('、') || '未选择目标')

const sourceTypeLabels: Record<string, string> = {
  public_suggestion: '提交建议',
  suggestion_reply: '回复发件人',
  rectification_task: '下发整改',
  system: '站内消息',
  manual: '站内消息',
}

const inboxStatusTabs = computed(() => {
  const count = (status?: string) => status
    ? publicSuggestions.value.filter((message) => message.status === status).length
    : publicSuggestions.value.length
  return [
    { key: 'all' as const, label: '全部建议', count: count() },
    { key: 'pending_review' as const, label: '待处理', count: count('pending_review') },
    { key: 'replied' as const, label: '已回复', count: count('replied') },
    { key: 'forwarded' as const, label: '已转派', count: count('forwarded') },
    { key: 'closed' as const, label: '已办结', count: count('closed') },
  ]
})

const filteredSuggestions = computed(() => {
  if (activeInboxStatus.value === 'all') return publicSuggestions.value
  return publicSuggestions.value.filter((message) => message.status === activeInboxStatus.value)
})

const selectedSuggestion = computed(() => {
  if (!isInboxAdmin.value) return null
  const selected = filteredSuggestions.value.find((message) => message.id === selectedSuggestionId.value)
  return selected || filteredSuggestions.value[0] || null
})

const selectedSuggestionChildren = computed(() => {
  const current = selectedSuggestion.value
  if (!current) return []
  return messages.value
    .filter((message) => message.parent_id === current.id)
    .sort((left, right) => left.created_at.localeCompare(right.created_at))
})

const selectedSuggestionTimeline = computed(() => {
  const current = selectedSuggestion.value
  if (!current) return []
  const replyChildren = selectedSuggestionChildren.value.filter((message) => message.source_type === 'suggestion_reply')
  const timeline = [
    {
      id: `suggestion-${current.id}`,
      label: '提交建议',
      title: current.title,
      content: current.content,
      meta: `${roleLabels[current.sender_role] || current.sender_role} · ${current.created_at}`,
      note: current.review_note || '',
    },
    ...selectedSuggestionChildren.value.map((message) => ({
      id: `message-${message.id}`,
      label: sourceTypeLabels[message.source_type || ''] || '流转记录',
      title: message.title,
      content: message.content,
      meta: `${roleLabels[message.sender_role] || message.sender_role} · ${message.created_at}`,
      note: message.review_note || '',
    })),
  ]
  if (current.reply_content && !replyChildren.length) {
    timeline.push({
      id: `review-${current.id}`,
      label: '审核回复',
      title: '回复发件人',
      content: current.reply_content,
      meta: current.reviewed_at || current.created_at,
      note: current.review_note || '',
    })
  }
  return timeline
})

function draftFor(message: DispatchMessage) {
  if (!reviewDrafts[message.id]) {
    reviewDrafts[message.id] = {
      reply: message.reply_content || '',
      note: message.review_note || '',
      status: message.status === 'closed' ? 'closed' : 'replied',
      forwardTitle: `调查整改：${message.title}`,
      forwardContent: `请核查群众反馈事项并形成整改结果。\n\n原始建议：${message.content}`,
      roles: isCityAdmin.value ? ['county_admin', 'community_admin'] : ['community_admin'],
    }
  }
  return reviewDrafts[message.id]
}

const forwardRoleOptions = computed<Role[]>(() => isCityAdmin.value ? ['county_admin', 'community_admin'] : ['community_admin'])

function statusText(message: DispatchMessage) {
  return statusLabels[message.status || 'sent'] || message.priority
}

function formatFileSize(size: number) {
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${size || 0} B`
}

function onSuggestionFiles(event: Event) {
  const input = event.target as HTMLInputElement
  suggestionFiles.value = Array.from(input.files || []).slice(0, 5)
}

async function downloadAttachment(attachment: NonNullable<DispatchMessage['attachments']>[number]) {
  if (!attachment.url) return
  const response = await api.get(attachment.url, { responseType: 'blob' })
  const objectUrl = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = attachment.name
  link.click()
  URL.revokeObjectURL(objectUrl)
}

function selectSuggestion(message: DispatchMessage) {
  selectedSuggestionId.value = message.id
  draftFor(message)
}

function messageTargets(message: DispatchMessage) {
  return message.target_roles?.map((role) => roleLabels[role] || role).join('、') || '未设置'
}

async function load() {
  const { data } = await api.get('/api/messages/inbox')
  messages.value = [...data].sort((left, right) => right.created_at.localeCompare(left.created_at))
  if (isInboxAdmin.value) {
    const suggestions = filteredSuggestions.value.length ? filteredSuggestions.value : publicSuggestions.value
    if (!suggestions.some((message) => message.id === selectedSuggestionId.value)) {
      selectedSuggestionId.value = suggestions[0]?.id || null
    }
  }
}

async function send() {
  if (sending.value) return
  if (!form.title.trim() || !form.content.trim()) {
    sendNotice.value = '请先填写消息标题和内容。'
    return
  }
  if (!targets.value.length) {
    sendNotice.value = '请至少选择一个下发目标。'
    return
  }

  sending.value = true
  lastSentMessage.value = null
  sendNotice.value = '正在下发站内消息，请稍候...'

  try {
    const { data } = await api.post('/api/messages', {
      title: form.title.trim(),
      content: form.content.trim(),
      target_roles: targets.value,
      target_district: user?.role === 'city_admin' ? undefined : user?.district,
      target_community: user?.role === 'community_admin' ? user?.community : undefined,
    })
    lastSentMessage.value = data
    sendNotice.value = `站内消息已下发，目标：${targetSummary.value}。`
    await load()
  } catch (error: any) {
    sendNotice.value = error?.response?.data?.detail || '站内消息下发失败，请检查内容和目标范围后重试。'
  } finally {
    sending.value = false
  }
}

async function submitSuggestion() {
  if (suggestionSending.value) return
  if (!suggestionForm.title.trim() || !suggestionForm.content.trim()) {
    inboxNotice.value = '请填写建议标题和内容。'
    return
  }
  suggestionSending.value = true
  inboxNotice.value = '正在提交信息建议...'
  try {
    const payload = new FormData()
    payload.append('title', suggestionForm.title.trim())
    payload.append('content', suggestionForm.content.trim())
    payload.append('district', suggestionForm.district || user?.district || '')
    payload.append('community', suggestionForm.community || user?.community || '')
    suggestionFiles.value.forEach((file) => payload.append('files', file))
    await api.post('/api/messages/suggestions/upload', payload)
    suggestionForm.content = ''
    suggestionFiles.value = []
    inboxNotice.value = '信息建议已提交，市级与对应区县管理人员将在收件箱中处理。'
    await load()
  } catch (error: any) {
    inboxNotice.value = error?.response?.data?.detail || '信息建议提交失败，请稍后重试。'
  } finally {
    suggestionSending.value = false
  }
}

async function reviewMessage(message: DispatchMessage) {
  const draft = draftFor(message)
  activeSuggestionId.value = message.id
  try {
    await api.post(`/api/messages/${message.id}/review`, {
      status: draft.status,
      reply_content: draft.reply,
      review_note: draft.note,
    })
    inboxNotice.value = '审核回复已保存，提交人会在自己的消息中看到反馈。'
    await load()
  } catch (error: any) {
    inboxNotice.value = error?.response?.data?.detail || '审核回复失败，请稍后重试。'
  } finally {
    activeSuggestionId.value = null
  }
}

async function forwardRectification(message: DispatchMessage) {
  const draft = draftFor(message)
  const validRoles = draft.roles.filter((role) => forwardRoleOptions.value.includes(role))
  if (!draft.forwardTitle.trim() || !draft.forwardContent.trim() || !validRoles.length) {
    inboxNotice.value = '请填写整改任务标题、内容并选择下发对象。'
    return
  }
  activeSuggestionId.value = message.id
  try {
    await api.post(`/api/messages/${message.id}/forward-rectification`, {
      title: draft.forwardTitle.trim(),
      content: draft.forwardContent.trim(),
      target_roles: validRoles,
      target_district: message.target_district || user?.district || undefined,
      target_community: message.target_community || undefined,
    })
    inboxNotice.value = '已下发给区县/社区进行调查整改。'
    await load()
  } catch (error: any) {
    inboxNotice.value = error?.response?.data?.detail || '整改任务下发失败，请检查目标范围。'
  } finally {
    activeSuggestionId.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="page messages-page" :class="{ 'standalone-wide-layout': preserveStandaloneSplitLayout }">
    <div class="work-page-titlebar">
      <h1>{{ isAdmin ? '消息管理' : '我的消息' }}</h1>
      <WorkbenchBackButton v-if="isAdmin" />
    </div>

    <div class="message-workspace" :class="{ single: !isAdmin && !isPublicUser, 'public-message-workspace': isPublicUser, 'city-message-workspace': isInboxAdmin }">
      <article v-if="isAdmin" class="panel">
        <div class="section-head">
          <div>
            <h2>下发站内消息</h2>
            <p class="hint">用于向下级部门、居民和游客发布通知；市级端可在右侧统一处理公众建议。</p>
          </div>
        </div>
        <div class="incident-form">
          <label>标题<input v-model="form.title" :disabled="sending" /></label>
          <label>内容<textarea v-model="form.content" class="message-content-box" :disabled="sending" /></label>
          <div class="target-list compact-target-list">
            <label v-for="role in allowedTargets" :key="role" class="check-line">
              <input v-model="targets" type="checkbox" :value="role" :disabled="sending" />
              <span>{{ roleLabels[role] }}</span>
            </label>
          </div>
          <p class="message-target-summary">当前将下发给：{{ targetSummary }}</p>
          <button class="primary-button message-send-button" :disabled="sending" @click="send">
            <span v-if="sending" class="button-spinner light" aria-hidden="true"></span>
            {{ sending ? '正在下发...' : '下发站内消息' }}
          </button>
          <p v-if="sendNotice" class="notice message-send-notice">{{ sendNotice }}</p>
          <p v-if="lastSentMessage" class="message-send-summary">
            已生成消息 #{{ lastSentMessage.id }}，时间：{{ lastSentMessage.created_at }}
          </p>
        </div>
      </article>

      <article v-else-if="isPublicUser" class="panel suggestion-panel">
        <div class="section-head">
          <div>
            <h2>提交信息建议</h2>
            <p class="hint">可反馈预警文案、避险点、景区秩序、道路风险等问题，系统会提交给对应区县和市级管理端。</p>
          </div>
        </div>
        <div class="incident-form suggestion-form">
          <label>标题<input v-model="suggestionForm.title" :disabled="suggestionSending" /></label>
          <label>所属区县
            <select v-model="suggestionForm.district" :disabled="suggestionSending || !!user?.district">
              <option v-for="district in ['永定区', '武陵源区', '慈利县', '桑植县']" :key="district" :value="district">{{ district }}</option>
            </select>
          </label>
          <label>所属社区/位置<input v-model="suggestionForm.community" :disabled="suggestionSending" placeholder="如所在社区、景区或道路位置" /></label>
          <label class="suggestion-content-field">内容<textarea v-model="suggestionForm.content" class="message-content-box" :disabled="suggestionSending" placeholder="请描述发现的问题、所在位置、建议改进方向..." /></label>
          <label class="suggestion-file-field">上传文件
            <input type="file" multiple :disabled="suggestionSending" @change="onSuggestionFiles" />
          </label>
          <div v-if="suggestionFiles.length" class="message-attachment-list">
            <span v-for="file in suggestionFiles" :key="`${file.name}-${file.size}`">{{ file.name }} · {{ formatFileSize(file.size) }}</span>
          </div>
          <button class="primary-button message-send-button" :disabled="suggestionSending" @click="submitSuggestion">
            <span v-if="suggestionSending" class="button-spinner light" aria-hidden="true"></span>
            {{ suggestionSending ? '正在提交...' : '提交信息和文件' }}
          </button>
        </div>
      </article>

      <article class="panel" :class="{ 'city-inbox-panel': isInboxAdmin }">
        <div class="section-head">
          <div>
            <h1>{{ isInboxAdmin ? '我的收件箱' : '我的消息' }}</h1>
            <p v-if="isInboxAdmin" class="hint">居民和游客提交的信息建议在这里审核、回复，并可下发给区县和社区整改。</p>
          </div>
          <button class="ghost-button" @click="load">刷新</button>
        </div>
        <p v-if="inboxNotice" class="notice">{{ inboxNotice }}</p>

        <div v-if="isInboxAdmin" class="inbox-status-tabs">
          <button
            v-for="tab in inboxStatusTabs"
            :key="tab.key"
            :class="{ active: activeInboxStatus === tab.key }"
            @click="activeInboxStatus = tab.key"
          >
            <span>{{ tab.label }}</span>
            <strong>{{ tab.count }}</strong>
          </button>
        </div>

        <div v-if="isInboxAdmin" class="city-inbox-board">
          <aside class="city-inbox-sidebar">
            <div class="suggestion-history-list">
              <div class="suggestion-list-head">
                <h3>建议目录</h3>
                <small>{{ filteredSuggestions.length }} 条</small>
              </div>
              <div v-if="!filteredSuggestions.length" class="notice">暂无历史建议。</div>
              <button
                v-for="message in filteredSuggestions"
                :key="message.id"
                class="suggestion-history-item"
                :class="{ active: selectedSuggestion?.id === message.id }"
                @click="selectSuggestion(message)"
              >
                <span class="level">{{ statusText(message) }}</span>
                <strong>{{ message.title }}</strong>
                <small>{{ roleLabels[message.sender_role] || message.sender_role }} · {{ message.created_at }}</small>
              </button>
            </div>
          </aside>

          <section v-if="selectedSuggestion" class="suggestion-detail-board">
            <div class="inbox-action-tabs">
              <button :class="{ active: activeCityInboxSection === 'suggestions' }" @click="activeCityInboxSection = 'suggestions'">详情</button>
              <button :class="{ active: activeCityInboxSection === 'history' }" @click="activeCityInboxSection = 'history'">流转</button>
              <button :class="{ active: activeCityInboxSection === 'reply' }" @click="activeCityInboxSection = 'reply'">回复</button>
              <button :class="{ active: activeCityInboxSection === 'forward' }" @click="activeCityInboxSection = 'forward'">转派</button>
            </div>
            <div v-if="activeCityInboxSection === 'suggestions'" class="suggestion-detail-card">
              <div class="message-card-head">
                <span class="level">{{ statusText(selectedSuggestion) }}</span>
                <small>{{ roleLabels[selectedSuggestion.sender_role] || selectedSuggestion.sender_role }} · {{ selectedSuggestion.created_at }}</small>
              </div>
              <h2>{{ selectedSuggestion.title }}</h2>
              <p>{{ selectedSuggestion.content }}</p>
              <div v-if="selectedSuggestion.attachments?.length" class="message-attachment-list inbox-attachment-list">
                <button
                  v-for="attachment in selectedSuggestion.attachments"
                  :key="attachment.id"
                  type="button"
                  @click="downloadAttachment(attachment)"
                >
                  {{ attachment.name }} · {{ formatFileSize(attachment.size) }}
                </button>
              </div>
              <dl class="message-meta-grid">
                <div>
                  <dt>来源身份</dt>
                  <dd>{{ roleLabels[selectedSuggestion.sender_role] || selectedSuggestion.sender_role }}</dd>
                </div>
                <div>
                  <dt>提交区域</dt>
                  <dd>{{ selectedSuggestion.target_district || '未填写' }}</dd>
                </div>
                <div>
                  <dt>所属社区</dt>
                  <dd>{{ selectedSuggestion.target_community || '未填写' }}</dd>
                </div>
                <div>
                  <dt>最近审核</dt>
                  <dd>{{ selectedSuggestion.reviewed_at || '尚未审核' }}</dd>
                </div>
              </dl>
            </div>

            <div v-if="activeCityInboxSection === 'history'" class="suggestion-history-timeline">
              <h3>提交/回复历史</h3>
              <div v-for="item in selectedSuggestionTimeline" :key="item.id" class="timeline-item message-timeline-item">
                <span>{{ item.label }}</span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.meta }}</small>
                <p>{{ item.content }}</p>
                <em v-if="item.note">备注：{{ item.note }}</em>
              </div>
            </div>

            <section v-if="activeCityInboxSection === 'reply'" class="review-box city-action-box">
              <h3>回复发件人</h3>
              <label>回复内容<textarea v-model="draftFor(selectedSuggestion).reply" class="review-reply-box" placeholder="填写给居民或游客的回复内容" /></label>
              <label>审核备注<textarea v-model="draftFor(selectedSuggestion).note" class="review-note-box" placeholder="内部处理备注，可为空" /></label>
              <label>处理状态
                <select v-model="draftFor(selectedSuggestion).status">
                  <option value="replied">已回复</option>
                  <option value="closed">已办结</option>
                </select>
              </label>
              <button class="primary-button" :disabled="activeSuggestionId === selectedSuggestion.id" @click="reviewMessage(selectedSuggestion)">保存回复</button>
            </section>

            <section v-if="activeCityInboxSection === 'forward'" class="rectification-box city-action-box">
              <div class="city-action-head">
                <div>
                  <h3>下发下级任务</h3>
                  <p>将需要调查整改的问题转给区县或社区处理。</p>
                </div>
              </div>
              <div class="city-forward-form">
                <label>任务标题<input v-model="draftFor(selectedSuggestion).forwardTitle" /></label>
                <label>任务内容<textarea v-model="draftFor(selectedSuggestion).forwardContent" class="rectification-content-box" /></label>
              </div>
              <div class="forward-target-box">
                <span>下发对象</span>
                <div class="target-list compact-target-list">
                  <label v-for="role in forwardRoleOptions" :key="role" class="check-line">
                    <input v-model="draftFor(selectedSuggestion).roles" type="checkbox" :value="role" />
                    <span>{{ roleLabels[role] }}</span>
                  </label>
                </div>
              </div>
              <div class="city-action-footer">
                <p class="message-target-summary">当前下发对象：{{ messageTargets({ ...selectedSuggestion, target_roles: draftFor(selectedSuggestion).roles }) }}</p>
                <button class="ghost-button" :disabled="activeSuggestionId === selectedSuggestion.id" @click="forwardRectification(selectedSuggestion)">下发整改任务</button>
              </div>
            </section>
          </section>
        </div>

        <template v-else>
          <div v-if="!visibleInbox.length" class="notice">暂无可见消息。</div>
          <div v-for="message in visibleInbox" :key="message.id" class="alert-card message-card">
            <div class="message-card-head">
              <span class="level">{{ statusLabels[message.status || 'sent'] || message.priority }}</span>
              <small>{{ roleLabels[message.sender_role] || message.sender_role }} · {{ message.created_at }}</small>
            </div>
            <h3>{{ message.title }}</h3>
            <p>{{ message.content }}</p>
            <div v-if="message.attachments?.length" class="message-attachment-list inbox-attachment-list">
              <button
                v-for="attachment in message.attachments"
                :key="attachment.id"
                type="button"
                @click="downloadAttachment(attachment)"
              >
                {{ attachment.name }} · {{ formatFileSize(attachment.size) }}
              </button>
            </div>
            <p v-if="message.reply_content" class="message-reply">回复：{{ message.reply_content }}</p>
          </div>
        </template>
      </article>
    </div>
  </section>
</template>
