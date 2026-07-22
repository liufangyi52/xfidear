<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Building2, Landmark, Trees } from 'lucide-vue-next'
import { api } from '../api'
import { destinationFor, setSession } from '../auth'
import loginBrandMark from '../assets/login-brand-mark.png'
import type { Role } from '../types'

const router = useRouter()
const mode = ref<'login' | 'register'>('login')
const activeRole = ref<Role>('city_admin')
const notice = ref('')

const adminRoles: Role[] = ['city_admin', 'county_admin', 'community_admin']
const districts = ['永定区', '武陵源区', '桑植县', '慈利县']
const demoAccounts: Record<Role, { username: string; password: string; district?: string; community?: string }> = {
  city_admin: { username: 'city_demo', password: '123456' },
  county_admin: { username: 'county_admin_demo', password: '123456', district: '武陵源区' },
  community_admin: { username: 'community_admin_demo', password: '123456', district: '武陵源区', community: '标志门社区' },
  resident: { username: 'resident_demo', password: '123456', district: '武陵源区' },
  tourist: { username: 'tourist_demo', password: '123456' },
}
const roleCards = [
  { role: 'city_admin' as Role, title: '张家界市应急管理部门人员', desc: '全市级指挥调度与监测', icon: Landmark },
  { role: 'county_admin' as Role, title: '区县级应急管理部门人员', desc: '永定区、武陵源区、桑植县、慈利县', icon: Building2 },
  { role: 'community_admin' as Role, title: '社区/村干部', desc: '村社区级现场调度与通知', icon: Trees },
]

const form = reactive({
  username: demoAccounts.city_admin.username,
  password: demoAccounts.city_admin.password,
  district: '武陵源区',
  community: '标志门社区',
})

const needsDistrict = computed(() => activeRole.value !== 'city_admin')
const needsCommunity = computed(() => activeRole.value === 'community_admin')
function selectRole(role: Role) {
  activeRole.value = role
  mode.value = 'login'
  notice.value = ''
  const account = demoAccounts[role]
  form.username = account.username
  form.password = account.password
  form.district = account.district || '武陵源区'
  form.community = account.community || '标志门社区'
}

function selectedActiveScope() {
  return {
    activeDistrict: needsDistrict.value ? form.district : undefined,
    activeCommunity: needsCommunity.value ? form.community : undefined,
    scopeSource: 'login_selection' as const,
  }
}

async function submit() {
  notice.value = ''
  const payload = {
    username: form.username,
    password: form.password,
    role: activeRole.value,
    district: needsDistrict.value ? form.district : undefined,
    community: needsCommunity.value ? form.community : undefined,
  }

  try {
    const { data } =
      mode.value === 'register'
        ? await api.post('/api/auth/register', payload)
        : await api.post('/api/auth/login', { username: form.username, password: form.password })

    setSession(data.token, data.user, selectedActiveScope())
    if (adminRoles.includes(data.user.role)) {
      localStorage.setItem('command_workbench_mode', 'bigscreen')
    }
    router.push(destinationFor())
  } catch (error: any) {
    notice.value = error?.response?.data?.detail || (mode.value === 'login' ? '登录失败，请检查账号和密码。' : '注册失败，请检查输入。')
  }
}
</script>

<template>
  <section class="login-portal-screen">
    <div class="login-portal-noise" aria-hidden="true"></div>
    <div class="login-portal-stage">
      <header class="login-hero">
        <div class="login-brand-line">
          <div class="login-brand-mark" aria-hidden="true">
            <img :src="loginBrandMark" alt="" />
          </div>
          <h1>张家界 <span>•</span> 智瞳应急平台</h1>
          <p>AI + 城市 · 分级应急调度入口</p>
        </div>
        <p class="login-hero-copy">
          市级、区县级、社区村干部按角色进入，形成预警发布、站内消息触达、现场上报、指挥处置、AI 研判、语音播报与辅助复盘闭环。
        </p>
      </header>

      <div class="login-role-row">
        <button
          v-for="card in roleCards"
          :key="card.role"
          type="button"
          :class="['login-role-card', { active: activeRole === card.role }]"
          @click="selectRole(card.role)"
        >
          <component :is="card.icon" :size="23" :stroke-width="2.1" />
          <div class="login-role-copy">
            <strong>{{ card.title }}</strong>
            <span>{{ card.desc }}</span>
          </div>
        </button>
      </div>

      <form class="login-auth-card" @submit.prevent="submit">
        <div class="login-auth-switch">
          <button type="button" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
          <button type="button" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
        </div>
        <label class="login-field">
          <span>账号</span>
          <input v-model="form.username" autocomplete="username" />
        </label>

        <label class="login-field">
          <span>密码</span>
          <input
            v-model="form.password"
            type="password"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          />
        </label>

        <label v-if="mode === 'register' && needsDistrict" class="login-field">
          <span>所属区县</span>
          <select v-model="form.district">
            <option v-for="district in districts" :key="district">{{ district }}</option>
          </select>
        </label>

        <label v-if="mode === 'register' && needsCommunity" class="login-field">
          <span>社区/村</span>
          <input v-model="form.community" />
        </label>

        <button class="login-submit" type="submit">{{ mode === 'login' ? '进入系统' : '注册并进入' }}</button>
        <p v-if="notice" class="login-auth-notice">{{ notice }}</p>
      </form>
    </div>
  </section>
</template>
