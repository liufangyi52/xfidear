<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Mic, Send, Wand2 } from 'lucide-vue-next'
import { api } from '../api'
import { useAIChat } from '../composables/useAIChat'
import { useSpeech } from '../composables/useSpeech'
import type { Incident } from '../types'

const { ask, fallbackNotice, loading } = useAIChat()
const { speak, activate, message } = useSpeech()
const question = ref('暴雨来了怎么办？')
const messages = ref<{ role: 'user' | 'assistant'; text: string }[]>([
  { role: 'assistant', text: '可以直接问我张家界景区暴雨、山洪、滑坡、索道停运或安置点相关问题。也可以选择现场事件，让 AI 生成研判和处置建议。' },
])
const incidents = ref<Incident[]>([])
const selectedIncidentId = ref<number | ''>('')
const analysisText = ref('')
const analysisLoading = ref(false)

async function send() {
  if (!question.value.trim()) return
  const text = question.value
  messages.value.push({ role: 'user', text })
  question.value = ''
  const answer = await ask(text)
  messages.value.push({ role: 'assistant', text: answer.text })
}

async function loadIncidents() {
  const { data } = await api.get('/api/incidents').catch(() => ({ data: { items: [] } }))
  incidents.value = data.items || []
}

async function analyzeIncident() {
  analysisLoading.value = true
  try {
    const payload = selectedIncidentId.value
      ? { incident_id: selectedIncidentId.value }
      : { description: question.value || '金鞭溪水位上涨，有游客滞留，请生成研判。' }
    const { data } = await api.post('/api/incidents/analyze', payload)
    analysisText.value = data.text
    if (data.fallback_used) {
      messages.value.push({ role: 'assistant', text: '当前 AI 使用备用模式，回答质量可能有波动。' })
    }
  } finally {
    analysisLoading.value = false
  }
}

onMounted(loadIncidents)
</script>

<template>
  <section class="page chat-page">
    <div class="page-head">
      <p class="eyebrow">AI Assistant</p>
      <h1>AI 避险问答</h1>
    </div>
    <p v-if="fallbackNotice" class="notice">{{ fallbackNotice }}</p>
    <div class="quick-prompts">
      <button @click="question = '天门山索道下雨会关闭吗？'; send()">天门山索道下雨会关闭吗？</button>
      <button @click="question = '金鞭溪涨水怎么办？'; send()">金鞭溪涨水怎么办？</button>
      <button @click="question = '道路中断以后游客该去哪里？'; send()">道路中断以后游客该去哪里？</button>
    </div>

    <article class="panel incident-ai-panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Incident Analysis</p>
          <h2>事件 AI 研判</h2>
        </div>
        <button @click="analyzeIncident"><Wand2 :size="16" />生成研判</button>
      </div>
      <label>选择现场事件
        <select v-model="selectedIncidentId">
          <option value="">使用下方问题/描述</option>
          <option v-for="incident in incidents" :key="incident.id" :value="incident.id">
            #{{ incident.id }} {{ incident.scenic_area || incident.district }} · {{ incident.description }}
          </option>
        </select>
      </label>
      <p v-if="analysisLoading" class="hint">AI 正在分析现场事件...</p>
      <div v-if="analysisText" class="analysis-box">
        <p>{{ analysisText }}</p>
        <button class="ghost-button" @click="speak(analysisText)"><Mic :size="16" />播放研判</button>
      </div>
    </article>

    <div class="chat-window">
      <article v-for="(item, index) in messages" :key="index" :class="['bubble', item.role]">
        <p>{{ item.text }}</p>
        <button v-if="item.role === 'assistant'" class="icon-button" @click="speak(item.text)" title="播放回答"><Mic :size="16" /></button>
      </article>
      <p v-if="loading" class="hint">AI 正在生成避险建议...</p>
    </div>
    <div class="chat-input">
      <input v-model="question" @keyup.enter="send" placeholder="输入你的问题或事件描述" />
      <button @click="send"><Send :size="18" />发送</button>
    </div>
    <button class="ghost-button" @click="activate">🎤 允许语音</button>
    <p v-if="message" class="hint">{{ message }}</p>
  </section>
</template>
