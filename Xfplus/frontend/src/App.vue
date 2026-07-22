<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { Bot, LogOut } from 'lucide-vue-next'
import SmartEyeFloatingButton from './components/SmartEyeFloatingButton.vue'
import { clearSession, loadSession } from './auth'
import { navItemsFor } from './workflows'

const route = useRoute()
const router = useRouter()
const aiVisible = ref(localStorage.getItem('smart_eye_hidden') !== '1')
const toast = ref('')
let toastTimer: number | undefined
const user = computed(() => {
  route.path
  return loadSession()
})
const isPortal = computed(() => route.path === '/')
const isResidentHome = computed(() => route.path === '/app')
const isEmbedded = computed(() => route.query.embedded === '1' && window.parent !== window)
const navItems = computed(() => navItemsFor(user.value))
const showAiNavToggle = computed(() => !user.value?.role?.includes('admin'))

function broadcastAiState() {
  window.dispatchEvent(new CustomEvent('smart-eye-state', { detail: aiVisible.value }))
}

function logout() {
  clearSession()
  router.push('/')
}

function toggleAi() {
  aiVisible.value = !aiVisible.value
  if (aiVisible.value) {
    localStorage.removeItem('smart_eye_position')
    localStorage.removeItem('smart_eye_position_v2')
  }
  localStorage.setItem('smart_eye_hidden', aiVisible.value ? '0' : '1')
  broadcastAiState()
}

function hideAi() {
  aiVisible.value = false
  localStorage.setItem('smart_eye_hidden', '1')
  broadcastAiState()
}

function handleAiVisibility(event: Event) {
  const action = (event as CustomEvent<'toggle' | 'show' | 'hide'>).detail
  if (action === 'show') {
    aiVisible.value = true
    localStorage.setItem('smart_eye_hidden', '0')
    broadcastAiState()
    return
  }
  if (action === 'hide') {
    hideAi()
    return
  }
  toggleAi()
}

function showToast(event: Event) {
  toast.value = (event as CustomEvent<string>).detail
  if (toastTimer) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toast.value = ''
  }, 2800)
}

onMounted(() => {
  window.addEventListener('app-toast', showToast)
  window.addEventListener('smart-eye-visibility', handleAiVisibility as EventListener)
  broadcastAiState()
})
onUnmounted(() => {
  window.removeEventListener('app-toast', showToast)
  window.removeEventListener('smart-eye-visibility', handleAiVisibility as EventListener)
  if (toastTimer) window.clearTimeout(toastTimer)
})
</script>

<template>
  <div class="app-shell" :class="{ 'portal-shell': isPortal, 'resident-home-shell': isResidentHome, 'embedded-shell': isEmbedded }">
    <header v-if="!isPortal && !isEmbedded" class="topbar">
      <RouterLink :to="navItems[0]?.path || '/app'" class="brand" aria-label="返回默认工作台">
        <span class="brand-mark">瞳</span>
        <span>张家界·智瞳应急平台</span>
      </RouterLink>
      <nav class="desktop-nav" aria-label="主导航">
        <RouterLink v-for="item in navItems" :key="item.label" :to="item.path || '/app'">{{ item.label }}</RouterLink>
        <button v-if="showAiNavToggle" class="ghost-button slim" @click="toggleAi"><Bot :size="16" />{{ aiVisible ? '隐藏 AI 助手' : '显示 AI 助手' }}</button>
        <button class="ghost-button slim" @click="logout"><LogOut :size="16" />退出</button>
      </nav>
    </header>

    <main>
      <RouterView />
    </main>

    <nav v-if="!isPortal && !isEmbedded" class="bottom-tabs" aria-label="移动端导航">
      <RouterLink v-for="item in navItems.slice(0, 5)" :key="item.label" :to="item.path || '/app'">
        <span>{{ item.label }}</span>
      </RouterLink>
      <button v-if="showAiNavToggle" class="tab-button" @click="toggleAi">{{ aiVisible ? '隐藏AI' : '显示AI' }}</button>
    </nav>

    <SmartEyeFloatingButton v-if="!isPortal && !isEmbedded && aiVisible" @hide="hideAi" />
    <div v-if="toast" class="app-toast">{{ toast }}</div>

    <footer v-if="!isPortal && !isEmbedded" class="source-footer">
      <span>天气数据优先由高德地图天气 API 提供，地图底图使用高德地图 API，地质灾害点信息根据政府公开资料整理。</span>
      <span>比赛可上线运行版，数据基于公开资料与真实流程建模，不替代政府正式应急系统。</span>
      <span>© 2026 张家界·智瞳应急平台</span>
    </footer>
  </div>
</template>
