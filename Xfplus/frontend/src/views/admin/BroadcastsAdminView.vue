<script setup lang="ts">
import { onMounted, ref } from 'vue'
import WorkbenchBackButton from '../../components/WorkbenchBackButton.vue'
import { api } from '../../api'
import { useSpeech } from '../../composables/useSpeech'

const records = ref<any[]>([])
const { speak, stop } = useSpeech()
const activeBroadcastKey = ref<string | null>(null)
const expandedBroadcastKeys = ref<Set<string>>(new Set())

function broadcastLines(content: string) {
  return String(content || '').split(/\n+/).map((line) => line.trim()).filter(Boolean)
}

function broadcastKey(record: any) {
  return String(record.id)
}

function isBroadcastExpanded(record: any) {
  return expandedBroadcastKeys.value.has(broadcastKey(record))
}

function toggleBroadcastContent(record: any) {
  const key = broadcastKey(record)
  const next = new Set(expandedBroadcastKeys.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedBroadcastKeys.value = next
}

function toggleBroadcast(record: any) {
  const key = broadcastKey(record)
  if (activeBroadcastKey.value === key) {
    stopBroadcast()
    return
  }
  activeBroadcastKey.value = key
  window.setTimeout(() => {
    if (activeBroadcastKey.value === key) {
      speak(record.content || record.alert_title || '')
    }
  }, 0)
}

function stopBroadcast() {
  stop()
  activeBroadcastKey.value = null
}

onMounted(async () => {
  records.value = (await api.get('/api/broadcasts')).data
})
</script>

<template>
  <section class="admin-page admin-page-full">
    <div class="admin-content">
      <div class="work-page-titlebar">
        <h1>广播管理</h1>
        <WorkbenchBackButton />
      </div>
      <div class="panel broadcast-panel">
        <div v-for="record in records" :key="record.id" class="admin-row broadcast-row">
          <div class="broadcast-main">
            <strong>{{ record.alert_title || '站内广播记录' }}</strong>
            <small>{{ record.type }} · {{ record.audience }} · {{ record.created_at }}</small>
            <div v-if="isBroadcastExpanded(record)" class="broadcast-content">
              <p v-for="(line, index) in broadcastLines(record.content)" :key="index">{{ line }}</p>
            </div>
          </div>
          <div class="broadcast-actions">
            <button type="button" class="ghost-button" @click="toggleBroadcastContent(record)">
              {{ isBroadcastExpanded(record) ? '收起内容' : '展开内容' }}
            </button>
            <button
              type="button"
              :class="{ 'ghost-button': activeBroadcastKey === broadcastKey(record) }"
              @click="toggleBroadcast(record)"
            >
              {{ activeBroadcastKey === broadcastKey(record) ? '关闭播报' : '语音播报' }}
            </button>
          </div>
        </div>
        <p class="hint">讯飞 TTS 生成 MP3 为二期增强，首版使用 Web Speech API 完成浏览器语音播报。</p>
      </div>
    </div>
  </section>
</template>
