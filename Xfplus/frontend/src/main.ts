import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'leaflet/dist/leaflet.css'
import './style.css'
import App from './App.vue'
import { router } from './router'

function recoverFromStaleAssets() {
  const refreshKey = 'zjj_asset_refresh_attempted'
  const shouldReload = (reason: unknown) => {
    const message = reason instanceof Error ? reason.message : String(reason || '')
    return (
      message.includes('Failed to fetch dynamically imported module') ||
      message.includes('Importing a module script failed') ||
      message.includes('error loading dynamically imported module')
    )
  }
  const reloadOnce = () => {
    if (sessionStorage.getItem(refreshKey) === '1') return
    sessionStorage.setItem(refreshKey, '1')
    const url = new URL(window.location.href)
    url.searchParams.set('_asset_refresh', Date.now().toString())
    window.location.replace(url.toString())
  }

  window.addEventListener('vite:preloadError', (event) => {
    event.preventDefault()
    reloadOnce()
  })
  window.addEventListener('unhandledrejection', (event) => {
    if (shouldReload(event.reason)) reloadOnce()
  })
  window.addEventListener('load', () => {
    if (new URL(window.location.href).searchParams.has('_asset_refresh')) {
      sessionStorage.removeItem(refreshKey)
    }
  })
}

recoverFromStaleAssets()
createApp(App).use(createPinia()).use(router).mount('#app')
