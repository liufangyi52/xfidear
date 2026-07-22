import type { Role, User } from './types'

export interface NavItem {
  label: string
  path?: string
  key?: string
}

export function commandPath(user: User | null) {
  if (user?.role === 'city_admin') return '/command/city'
  if (user?.role === 'county_admin') return '/command/county'
  if (user?.role === 'community_admin') return '/command/community'
  return '/app'
}

export function workbenchPathForRole(role?: Role) {
  if (role === 'city_admin') return '/command/city'
  if (role === 'county_admin') return '/command/county'
  if (role === 'community_admin') return '/command/community'
  return '/app'
}

export function defaultPathForRole(role?: Role) {
  return workbenchPathForRole(role)
}

export function navItemsFor(user: User | null): NavItem[] {
  if (!user) return []
  if (user.role === 'city_admin' || user.role === 'county_admin') {
    return [{ label: '工作台', path: commandPath(user) }]
  }
  if (user.role === 'community_admin') {
    return [{ label: '工作台', path: commandPath(user) }]
  }
  if (user.role === 'tourist') {
    return [
      { label: '游客首页', path: '/app' },
      { label: '景区地图', path: '/risk-map' },
      { label: '求助/SOS', path: '/report' },
      { label: '通知', path: '/messages' },
      { label: '行程设置', path: '/settings' },
    ]
  }
  return [
    { label: '首页', path: '/app' },
    { label: '风险地图', path: '/risk-map' },
    { label: '上报/SOS', path: '/report' },
    { label: '我的消息', path: '/messages' },
    { label: '设置', path: '/settings' },
  ]
}
