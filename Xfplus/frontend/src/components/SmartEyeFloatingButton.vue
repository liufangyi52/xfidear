<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, type StyleValue } from 'vue'
import { Bot, Minus, Send, X } from 'lucide-vue-next'
import { api } from '../api'
import { loadActiveScope, loadSession } from '../auth'

const emit = defineEmits<{ hide: [] }>()
const POS_KEY = 'smart_eye_position_v5'
const LEGACY_HISTORY_KEY = 'smart_eye_history'
const SIZE_KEY = 'smart_eye_panel_size'
const DEFAULT_PANEL_WIDTH = 380
const DEFAULT_PANEL_HEIGHT = 560
const BIGSCREEN_PANEL_WIDTH = 460
const saved = JSON.parse(localStorage.getItem(POS_KEY) || '{"x":null,"y":null}')
const savedSize = JSON.parse(localStorage.getItem(SIZE_KEY) || '{"width":380,"height":560}')
const position = ref<{ x: number | null; y: number | null }>({
  x: Number.isFinite(saved.x) ? saved.x : null,
  y: Number.isFinite(saved.y) ? saved.y : null,
})
const panelSize = ref({ width: savedSize.width || DEFAULT_PANEL_WIDTH, height: savedSize.height || DEFAULT_PANEL_HEIGHT })
const open = ref(false)
const question = ref('')
const loading = ref(false)
const fallbackNotice = ref('')
const introBubbleHover = ref(false)
const introBubblePinned = ref(false)
const chatRef = ref<HTMLElement | null>(null)
const rootRef = ref<HTMLElement | null>(null)
const avatarRef = ref<HTMLElement | null>(null)
const viewport = ref({ width: window.innerWidth, height: window.innerHeight })
const panelAnchor = ref({ left: 0, top: 0 })
const displayPanelSize = ref({ width: panelSize.value.width, height: panelSize.value.height })
const bigscreenTheme = ref(false)
const user = loadSession()
const activeScope = loadActiveScope()
const historyKey = scopedHistoryKey()
const messages = ref<{ role: 'user' | 'assistant'; content: string }[]>(
  JSON.parse(localStorage.getItem(historyKey) || '[]'),
)
let dragging = false
let moved = false
let startX = 0
let startY = 0
let originX = 0
let originY = 0
let longPressTimer: number | undefined
let dragPointerId: number | null = null
let dragPointerTarget: HTMLElement | null = null
let resizing = false
let resizeCorner: 'nw' | 'ne' | 'sw' | 'se' = 'se'
let resizeStartX = 0
let resizeStartY = 0
let resizeStartWidth = 0
let resizeStartHeight = 0
const VIEWPORT_EDGE = 12
const PANEL_GAP = 8

const quickPrompts = computed(() => {
  if (user?.role?.includes('admin')) return ['如何发布预警？', '分析当前待处置事件趋势', '如何组织转移安置？']
  return ['暴雨如何避险？', '附近安置点在哪里？', '地质灾害知识']
})
const introBubbleVisible = computed(() => introBubbleHover.value || introBubblePinned.value)
const introBubbleText = computed(() => '您好，我是智瞳，您的专属AI应急助手')

function scopedHistoryKey() {
  if (!user) return 'smart_eye_history:anonymous'
  const scope = [
    user.id,
    user.role,
    activeScope?.activeDistrict || user.district || 'all',
    activeScope?.activeCommunity || user.community || 'all',
  ]
    .map((item) => String(item).replace(/[^\w\u4e00-\u9fa5-]/g, '_'))
    .join(':')
  return `smart_eye_history:${scope}`
}

function styleForAvatar() {
  if (position.value.x === null || position.value.y === null) return {}
  return {
    left: `${position.value.x}px`,
    top: `${position.value.y}px`,
  }
}

function styleForPanel(): StyleValue {
  const inputHeight = Math.round(Math.min(94, Math.max(58, displayPanelSize.value.height * 0.11)))
  const sendWidth = Math.round(Math.min(96, Math.max(64, displayPanelSize.value.width * 0.13)))
  const panelGap = Math.round(Math.min(12, Math.max(8, displayPanelSize.value.width * 0.02)))
  return {
    position: 'fixed',
    zIndex: 1001,
    left: `${panelAnchor.value.left}px`,
    top: `${panelAnchor.value.top}px`,
    right: 'auto',
    bottom: 'auto',
    width: `${displayPanelSize.value.width}px`,
    height: `${displayPanelSize.value.height}px`,
    minHeight: `${displayPanelSize.value.height}px`,
    maxHeight: `${displayPanelSize.value.height}px`,
    '--smart-eye-input-height': `${inputHeight}px`,
    '--smart-eye-send-width': `${sendWidth}px`,
    '--smart-eye-gap': `${panelGap}px`,
  }
}

function defaultAvatarPosition() {
  const rootStyles = rootRef.value ? window.getComputedStyle(rootRef.value) : null
  const avatarRect = avatarRef.value?.getBoundingClientRect()
  const height = avatarRect?.height ?? (bigscreenTheme.value ? 64 : 72)
  const leftInset = Number.parseFloat(rootStyles?.left || '')
  const bottomInset = Number.parseFloat(rootStyles?.bottom || '')
  const x = Number.isFinite(leftInset) ? leftInset : VIEWPORT_EDGE
  const bottom = Number.isFinite(bottomInset) ? bottomInset : VIEWPORT_EDGE
  return {
    x,
    y: Math.max(VIEWPORT_EDGE, viewport.value.height - height - bottom),
  }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function targetPanelSize() {
  return bigscreenTheme.value
    ? { width: BIGSCREEN_PANEL_WIDTH, height: DEFAULT_PANEL_HEIGHT }
    : panelSize.value
}

function clampPanelSize() {
  const maxWidth = Math.max(320, viewport.value.width - VIEWPORT_EDGE * 2)
  const maxHeight = Math.max(420, viewport.value.height - VIEWPORT_EDGE * 2)
  panelSize.value.width = Math.min(maxWidth, Math.max(320, panelSize.value.width))
  panelSize.value.height = Math.min(maxHeight, Math.max(420, panelSize.value.height))
  localStorage.setItem(SIZE_KEY, JSON.stringify(panelSize.value))
  const baseSize = targetPanelSize()
  displayPanelSize.value = {
    width: Math.min(maxWidth, Math.max(320, baseSize.width)),
    height: Math.min(maxHeight, Math.max(420, baseSize.height)),
  }
}

function avatarRectForPosition(nextPosition = position.value) {
  const rect = avatarRef.value?.getBoundingClientRect()
  if (!rect) return null
  if (nextPosition.x === null || nextPosition.y === null || position.value.x === null || position.value.y === null) {
    return {
      left: rect.left,
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      width: rect.width,
      height: rect.height,
    }
  }
  const dx = nextPosition.x - position.value.x
  const dy = nextPosition.y - position.value.y
  return {
    left: rect.left + dx,
    top: rect.top + dy,
    right: rect.right + dx,
    bottom: rect.bottom + dy,
    width: rect.width,
    height: rect.height,
  }
}

function updatePanelAnchor(nextPosition = position.value) {
  const rect = avatarRectForPosition(nextPosition)
  if (!rect) return
  const spaceAbove = Math.max(0, rect.top - PANEL_GAP - VIEWPORT_EDGE)
  const spaceBelow = Math.max(0, viewport.value.height - rect.bottom - PANEL_GAP - VIEWPORT_EDGE)
  const openAbove = spaceAbove >= spaceBelow
  const availableHeight = Math.max(260, openAbove ? spaceAbove : spaceBelow)
  const availableWidth = Math.max(320, viewport.value.width - VIEWPORT_EDGE * 2)
  const baseSize = targetPanelSize()
  const width = Math.min(Math.max(320, baseSize.width), availableWidth)
  const height = Math.min(Math.max(420, baseSize.height), availableHeight)
  displayPanelSize.value = { width, height }

  const rawTop = openAbove
    ? rect.top - height - PANEL_GAP
    : rect.bottom + PANEL_GAP
  const rawLeft = rect.left + rect.width / 2 > viewport.value.width / 2
    ? rect.right - width
    : rect.left

  panelAnchor.value = {
    left: clamp(rawLeft, VIEWPORT_EDGE, viewport.value.width - width - VIEWPORT_EDGE),
    top: clamp(rawTop, VIEWPORT_EDGE, viewport.value.height - height - VIEWPORT_EDGE),
  }
}

function scrollChatToBottom(behavior: ScrollBehavior = 'smooth') {
  requestAnimationFrame(() => {
    const el = chatRef.value
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior })
  })
}

function clampPosition(nextPosition = position.value) {
  const rect = avatarRectForPosition(nextPosition)
  if (!rect) {
    position.value = nextPosition
    localStorage.setItem(POS_KEY, JSON.stringify(position.value))
    return
  }
  let nextX = nextPosition.x ?? rect.left
  let nextY = nextPosition.y ?? rect.top
  if (rect.left < VIEWPORT_EDGE) nextX += VIEWPORT_EDGE - rect.left
  if (rect.right > viewport.value.width - VIEWPORT_EDGE) nextX -= rect.right - (viewport.value.width - VIEWPORT_EDGE)
  if (rect.top < VIEWPORT_EDGE) nextY += VIEWPORT_EDGE - rect.top
  if (rect.bottom > viewport.value.height - VIEWPORT_EDGE) nextY -= rect.bottom - (viewport.value.height - VIEWPORT_EDGE)
  position.value = { x: nextX, y: nextY }
  localStorage.setItem(POS_KEY, JSON.stringify(position.value))
  updatePanelAnchor(position.value)
}

function clearLongPressTimer() {
  if (longPressTimer) {
    window.clearTimeout(longPressTimer)
    longPressTimer = undefined
  }
}

function beginDrag(event: PointerEvent, target: EventTarget | null) {
  if (resizing) return false
  if (event.pointerType === 'mouse' && event.button !== 0) return false
  introBubbleHover.value = false
  introBubblePinned.value = false
  dragging = true
  moved = false
  startX = event.clientX
  startY = event.clientY
  const currentRect = avatarRef.value?.getBoundingClientRect()
  originX = position.value.x ?? currentRect?.left ?? VIEWPORT_EDGE
  originY = position.value.y ?? currentRect?.top ?? VIEWPORT_EDGE
  if (position.value.x === null || position.value.y === null) {
    position.value = { x: originX, y: originY }
    localStorage.setItem(POS_KEY, JSON.stringify(position.value))
  }
  dragPointerId = event.pointerId
  dragPointerTarget = target instanceof HTMLElement ? target : null
  dragPointerTarget?.setPointerCapture?.(event.pointerId)
  document.body.style.userSelect = 'none'
  event.preventDefault()
  window.addEventListener('pointermove', pointerMove, { passive: false })
  window.addEventListener('pointerup', pointerUp)
  window.addEventListener('pointercancel', pointerUp)
  return true
}

function pointerDown(event: PointerEvent) {
  if (!beginDrag(event, event.currentTarget)) return
  longPressTimer = window.setTimeout(() => confirmHide(), 700)
}

function pointerMove(event: PointerEvent) {
  if (!dragging || (dragPointerId !== null && event.pointerId !== dragPointerId)) return
  const dx = event.clientX - startX
  const dy = event.clientY - startY
  if (Math.abs(dx) + Math.abs(dy) > 8) {
    moved = true
    clearLongPressTimer()
  }
  event.preventDefault()
  clampPosition({ x: originX + dx, y: originY + dy })
}

function pointerUp(event?: PointerEvent) {
  if (event && dragPointerId !== null && event.pointerId !== dragPointerId) return
  dragging = false
  clearLongPressTimer()
  if (dragPointerId !== null) {
    dragPointerTarget?.releasePointerCapture?.(dragPointerId)
  }
  dragPointerId = null
  dragPointerTarget = null
  document.body.style.userSelect = ''
  window.removeEventListener('pointermove', pointerMove)
  window.removeEventListener('pointerup', pointerUp)
  window.removeEventListener('pointercancel', pointerUp)
}

function avatarClick() {
  avatarRef.value?.removeAttribute('title')
  const wasMoved = moved
  moved = false
  if (wasMoved) return
  introBubblePinned.value = true
  syncVisualTheme()
  open.value = !open.value
  if (open.value) {
    updatePanelAnchor()
    nextTick(() => {
      updatePanelAnchor()
      scrollChatToBottom('auto')
    })
  }
}

function showIntroBubble() {
  avatarRef.value?.removeAttribute('title')
  introBubbleHover.value = true
}

function hideIntroBubbleHover() {
  introBubbleHover.value = false
}

function hideIntroBubble() {
  introBubbleHover.value = false
  introBubblePinned.value = false
}

function panelHeaderPointerDown(event: PointerEvent) {
  const target = event.target as HTMLElement | null
  if (target?.closest('button, textarea, input, select, a')) return
  beginDrag(event, event.currentTarget)
}

function resizePointerDown(corner: 'nw' | 'ne' | 'sw' | 'se', event: PointerEvent) {
  resizing = true
  resizeCorner = corner
  resizeStartX = event.clientX
  resizeStartY = event.clientY
  resizeStartWidth = panelSize.value.width
  resizeStartHeight = panelSize.value.height
  event.preventDefault()
  event.stopPropagation()
  window.addEventListener('pointermove', resizePointerMove)
  window.addEventListener('pointerup', resizePointerUp)
}

function resizePointerMove(event: PointerEvent) {
  if (!resizing) return
  const dx = event.clientX - resizeStartX
  const dy = event.clientY - resizeStartY
  panelSize.value = {
    width: resizeStartWidth + (resizeCorner.includes('e') ? dx : -dx),
    height: resizeStartHeight + (resizeCorner.includes('s') ? dy : -dy),
  }
  clampPanelSize()
  updatePanelAnchor()
  scrollChatToBottom('auto')
}

function resizePointerUp() {
  resizing = false
  window.removeEventListener('pointermove', resizePointerMove)
  window.removeEventListener('pointerup', resizePointerUp)
}

function confirmHide() {
  if (window.confirm('关闭 AI 助手？')) emit('hide')
}

function syncVisualTheme() {
  bigscreenTheme.value = Boolean(document.querySelector('.workbench-screen.is-bigscreen'))
}

function minimize() {
  open.value = false
  hideIntroBubble()
}

function closeAll() {
  open.value = false
  hideIntroBubble()
  emit('hide')
}

function handleDocumentPointerDown(event: PointerEvent) {
  const target = event.target as Node | null
  if (!target) return
  const insideRoot = !!rootRef.value?.contains(target)
  const insidePanel = !!target && target instanceof Element && !!target.closest('.smart-eye-panel')
  if (!insideRoot && !insidePanel) {
    hideIntroBubble()
  }
}

function handleWindowResize() {
  viewport.value = { width: window.innerWidth, height: window.innerHeight }
  syncVisualTheme()
  if (position.value.x === null || position.value.y === null) {
    position.value = defaultAvatarPosition()
    localStorage.setItem(POS_KEY, JSON.stringify(position.value))
  }
  clampPanelSize()
  clampPosition()
  updatePanelAnchor()
}

function renderMarkdown(text: string) {
  const escaped = text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  return escaped
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}

function saveHistory() {
  localStorage.removeItem(LEGACY_HISTORY_KEY)
  localStorage.setItem(historyKey, JSON.stringify(messages.value.slice(-5)))
}

async function ask(text = question.value) {
  const q = text.trim()
  if (!q || loading.value) return
  question.value = ''
  messages.value.push({ role: 'user', content: q })
  loading.value = true
  await nextTick()
  scrollChatToBottom()
  try {
    const { data } = await api.post('/api/ai/chat', {
      question: q,
      context_type: user?.role?.includes('admin') ? 'decision' : 'public_safety',
      history: messages.value.slice(-5),
      active_district: activeScope?.activeDistrict,
      active_community: activeScope?.activeCommunity,
      stream: false,
    })
    fallbackNotice.value = data.fallback_used ? '当前 AI 使用备用模式，回答质量可能有波动' : ''
    messages.value.push({ role: 'assistant', content: data.answer })
    saveHistory()
    await nextTick()
    scrollChatToBottom()
  } catch {
    messages.value.push({ role: 'assistant', content: 'AI 服务暂时不可用，请稍后重试。' })
  } finally {
    loading.value = false
    await nextTick()
    scrollChatToBottom()
  }
}

onMounted(() => {
  handleWindowResize()
  nextTick(() => avatarRef.value?.removeAttribute('title'))
  window.addEventListener('resize', handleWindowResize)
  window.addEventListener('pointerdown', handleDocumentPointerDown)
})

onUnmounted(() => {
  clearLongPressTimer()
  pointerUp()
  resizePointerUp()
  document.body.style.userSelect = ''
  window.removeEventListener('resize', handleWindowResize)
  window.removeEventListener('pointerdown', handleDocumentPointerDown)
})
</script>

<template>
  <div ref="rootRef" class="smart-eye" :style="styleForAvatar()" @pointerenter="showIntroBubble" @pointerleave="hideIntroBubbleHover">
    <transition name="smart-eye-intro">
      <div v-if="introBubbleVisible" class="smart-eye-intro" role="status" aria-live="polite">
        <span>{{ introBubbleText }}</span>
      </div>
    </transition>
    <button
      ref="avatarRef"
      class="smart-eye-avatar"
      title="智瞳 AI 助手"
      @pointerdown="pointerDown"
      @click="avatarClick"
      @contextmenu.prevent="closeAll"
    >
      <Bot :size="26" />
      <span>智瞳</span>
    </button>

    <Teleport to="body">
      <section v-if="open" class="smart-eye-panel" :class="{ 'bigscreen-theme': bigscreenTheme }" :style="styleForPanel()">
        <button class="smart-eye-resize nw" type="button" aria-label="Resize panel" @pointerdown="resizePointerDown('nw', $event)" />
        <button class="smart-eye-resize ne" type="button" aria-label="Resize panel" @pointerdown="resizePointerDown('ne', $event)" />
        <button class="smart-eye-resize sw" type="button" aria-label="Resize panel" @pointerdown="resizePointerDown('sw', $event)" />
        <button class="smart-eye-resize se" type="button" aria-label="Resize panel" @pointerdown="resizePointerDown('se', $event)" />
        <header @pointerdown="panelHeaderPointerDown">
          <div>
            <strong>智瞳 AI 助手</strong>
            <small>决策辅助 · 公众避险 · 灾害知识</small>
          </div>
          <button class="icon-button" @click="minimize"><Minus :size="16" /></button>
          <button class="icon-button danger-icon" @click="closeAll"><X :size="16" /></button>
        </header>
        <p v-if="fallbackNotice" class="notice">{{ fallbackNotice }}</p>
        <div class="smart-eye-prompts">
          <button v-for="prompt in quickPrompts" :key="prompt" @click="ask(prompt)">{{ prompt }}</button>
        </div>
        <div ref="chatRef" class="smart-eye-chat">
          <article v-for="(item, index) in messages" :key="index" :class="['smart-eye-msg', item.role]">
            <div v-html="renderMarkdown(item.content)"></div>
          </article>
          <p v-if="loading" class="hint">智瞳正在思考...</p>
        </div>
        <form class="smart-eye-input" @submit.prevent="ask()">
          <textarea v-model="question" placeholder="请输入问题，例如：暴雨如何避险？" />
          <button :disabled="loading"><Send :size="16" />发送</button>
        </form>
      </section>
    </Teleport>
  </div>
</template>
