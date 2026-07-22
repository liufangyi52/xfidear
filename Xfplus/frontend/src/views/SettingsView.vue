<script setup lang="ts">
import { useRouter } from 'vue-router'
import { clearSession, loadSession } from '../auth'

const router = useRouter()
const user = loadSession()
const isTourist = user?.role === 'tourist'
const roleName = isTourist ? '游客' : user?.role
const scopeLabel = isTourist ? '当前游览区县' : '区县'
const communityLabel = isTourist ? '行程/社区绑定' : '社区'

function logout() {
  clearSession()
  router.push('/')
}
</script>

<template>
  <section class="page narrow">
    <article class="panel">
      <p class="eyebrow">Settings</p>
      <h1>{{ isTourist ? '游客行程设置' : '设置' }}</h1>
      <div class="metric-grid">
        <div><small>账号</small><strong>{{ user?.username }}</strong></div>
        <div><small>角色</small><strong>{{ roleName }}</strong></div>
        <div><small>{{ scopeLabel }}</small><strong>{{ user?.district || '全市/当前位置' }}</strong></div>
        <div><small>{{ communityLabel }}</small><strong>{{ isTourist ? '临时游客，不绑定社区' : user?.community || '未绑定' }}</strong></div>
      </div>
      <p class="hint">
        {{ isTourist ? '游客端按当前位置和公开预警接收提醒；求助/SOS 会进入待核验流程，紧急情况请同时联系现场工作人员。' : 'AI 助手的显隐状态、位置和最近 5 条对话会保存在本机浏览器。' }}
      </p>
      <button class="danger-button wide" @click="logout">退出登录</button>
    </article>
  </section>
</template>
