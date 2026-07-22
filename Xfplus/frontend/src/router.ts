import { createRouter, createWebHistory } from 'vue-router'
import { loadSession } from './auth'
import { defaultPathForRole } from './workflows'

const AssistantRedirect = {
  template:
    '<section class="page narrow"><p class="notice">AI 助手已升级为悬浮助手，请点击右下角“智瞳”图标使用。</p></section>',
  mounted() {
    const user = loadSession()
    window.dispatchEvent(new CustomEvent('app-toast', { detail: 'AI 助手已升级为悬浮助手，请点击右下角图标使用' }))
    window.setTimeout(() => router.replace(defaultPathForRole(user?.role)), 900)
  },
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('./views/LoginPortalView.vue') },
    { path: '/app', component: () => import('./views/HomeView.vue'), meta: { requiresAuth: true } },
    { path: '/alerts', component: () => import('./views/AlertsView.vue'), meta: { requiresAuth: true } },
    { path: '/alerts/:id', component: () => import('./views/AlertDetailView.vue'), meta: { requiresAuth: true } },
    { path: '/assistant', component: AssistantRedirect, meta: { requiresAuth: true } },
    { path: '/risk-map', component: () => import('./views/RiskMapView.vue'), meta: { requiresAuth: true } },
    { path: '/report', component: () => import('./views/CitizenReportView.vue'), meta: { requiresAuth: true, citizenOnly: true } },
    { path: '/messages', component: () => import('./views/MessagesView.vue'), meta: { requiresAuth: true } },
    { path: '/settings', component: () => import('./views/SettingsView.vue'), meta: { requiresAuth: true } },
    { path: '/risk-data', component: () => import('./views/RiskDataView.vue'), meta: { requiresAuth: true, riskDataOnly: true } },
    { path: '/command/:level', component: () => import('./views/CommandMapView.vue'), meta: { requiresAuth: true, adminOnly: true } },
    { path: '/admin', redirect: '/admin/incidents', meta: { requiresAuth: true, adminOnly: true } },
    { path: '/admin/alerts', component: () => import('./views/admin/AlertsAdminView.vue'), meta: { requiresAuth: true, adminOnly: true } },
    { path: '/admin/incidents', component: () => import('./views/admin/IncidentsAdminView.vue'), meta: { requiresAuth: true, adminOnly: true } },
    { path: '/admin/broadcasts', component: () => import('./views/admin/BroadcastsAdminView.vue'), meta: { requiresAuth: true, adminOnly: true } },
    { path: '/admin/reports', component: () => import('./views/admin/ReportsAdminView.vue'), meta: { requiresAuth: true, adminOnly: true } },
    { path: '/admin/shelters', component: () => import('./views/admin/SheltersAdminView.vue'), meta: { requiresAuth: true, adminOnly: true } },
  ],
})

router.beforeEach((to) => {
  const user = loadSession()
  if (to.meta.requiresAuth && !user) return '/'
  if (
    user?.role?.includes('admin') &&
    to.query.embedded !== '1' &&
    ['/assistant', '/admin/alerts', '/admin/incidents', '/messages', '/admin/broadcasts', '/admin/reports', '/risk-data'].includes(to.path)
  ) return defaultPathForRole(user.role)
  if (to.meta.adminOnly && !user?.role?.includes('admin')) return '/app'
  if (to.meta.citizenOnly && user?.role?.includes('admin')) return defaultPathForRole(user.role)
  if (to.meta.riskDataOnly && !['city_admin', 'county_admin'].includes(user?.role || '')) return defaultPathForRole(user?.role)
})
