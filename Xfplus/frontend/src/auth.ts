import { api } from './api'
import type { User } from './types'

const TOKEN_KEY = 'zjj_token'
const USER_KEY = 'zjj_user'
const ACTIVE_SCOPE_KEY = 'zjj_active_scope'

export interface ActiveScope {
  activeDistrict?: string
  activeCommunity?: string
  scopeSource: 'login_selection' | 'user_profile'
}

function normalizeScope(scope?: Partial<ActiveScope> | null): ActiveScope | null {
  if (!scope?.activeDistrict && !scope?.activeCommunity) return null
  return {
    activeDistrict: scope.activeDistrict || undefined,
    activeCommunity: scope.activeCommunity || undefined,
    scopeSource: scope.scopeSource || 'login_selection',
  }
}

export function setSession(token: string, user: User, activeScope?: Partial<ActiveScope> | null) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  const normalizedScope = normalizeScope(activeScope)
  if (normalizedScope) {
    localStorage.setItem(ACTIVE_SCOPE_KEY, JSON.stringify(normalizedScope))
  } else {
    localStorage.removeItem(ACTIVE_SCOPE_KEY)
  }
  localStorage.removeItem('smart_eye_history')
  api.defaults.headers.common.Authorization = `Bearer ${token}`
}

export function loadSession() {
  const token = localStorage.getItem(TOKEN_KEY)
  const raw = localStorage.getItem(USER_KEY)
  if (token) api.defaults.headers.common.Authorization = `Bearer ${token}`
  return raw ? (JSON.parse(raw) as User) : null
}

export function loadActiveScope(): ActiveScope | null {
  const raw = localStorage.getItem(ACTIVE_SCOPE_KEY)
  if (raw) {
    try {
      return normalizeScope(JSON.parse(raw) as Partial<ActiveScope>)
    } catch {
      localStorage.removeItem(ACTIVE_SCOPE_KEY)
    }
  }
  const user = loadSession()
  return normalizeScope({
    activeDistrict: user?.district,
    activeCommunity: user?.community,
    scopeSource: 'user_profile',
  })
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(ACTIVE_SCOPE_KEY)
  localStorage.removeItem('smart_eye_history')
  delete api.defaults.headers.common.Authorization
}

export function destinationFor() {
  const user = loadSession()
  if (user?.role === 'city_admin') return '/command/city'
  if (user?.role === 'county_admin') return '/command/county'
  if (user?.role === 'community_admin') return '/command/community'
  return '/app'
}
