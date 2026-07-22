<script setup lang="ts">
import * as L from 'leaflet'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { ensureLeafletHeat } from '../leafletHeat'
import { addAmapLayers, amapAvailable, toAmapLatLng, toAmapLatLngTuple, ZHANGJIAJIE_CENTER, ZHANGJIAJIE_CITY_ZOOM } from '../mapLayers'
import type { Incident, RiskPoint } from '../types'

const mapEl = ref<HTMLDivElement | null>(null)
const selected = ref<RiskPoint | null>(null)
const selectedIncident = ref<Incident | null>(null)
const incidents = ref<Incident[]>([])
const mapNotice = ref('')
const router = useRouter()

const colorMap: Record<string, string> = {
  red: '#d92d20',
  orange: '#f97316',
  yellow: '#eab308',
  blue: '#2563eb',
}

const iconMap: Record<string, string> = {
  red: '高',
  orange: '中',
  yellow: '低',
  blue: '待观察',
}

const incidentLabels: Record<string, string> = {
  flood: '积水/山洪',
  landslide: '滑坡/落石',
  road: '道路中断',
  medical: '人员受伤',
  sos: 'SOS 求助',
  shelter: '安置需求',
  other: '其他',
}

const stats = computed(() => ({
  total: incidents.value.length,
  sos: incidents.value.filter((item) => item.type === 'sos').length,
  pending: incidents.value.filter((item) => item.status === 'pending').length,
  responding: incidents.value.filter((item) => item.status === 'responding').length,
}))

function incidentColor(incident: Incident) {
  if (incident.severity === 'critical') return '#dc2626'
  if (incident.severity === 'high') return '#f97316'
  if (incident.severity === 'medium') return '#eab308'
  return '#0f766e'
}

onMounted(async () => {
  await ensureLeafletHeat()
  const [riskRes, incidentRes] = await Promise.all([
    api.get('/api/risk/current'),
    api.get('/api/incidents').catch(() => ({ data: { items: [] } })),
  ])
  incidents.value = incidentRes.data.items || []

  const map = L.map(mapEl.value as HTMLElement, { zoomControl: false }).setView(
    toAmapLatLngTuple(ZHANGJIAJIE_CENTER[0], ZHANGJIAJIE_CENTER[1]),
    ZHANGJIAJIE_CITY_ZOOM,
  )
  if (!addAmapLayers(map)) {
    mapNotice.value = '高德地图底图暂不可用；风险点和事件数据仍可查看。'
  }

  const heatData = [
    ...riskRes.data.points.map((point: RiskPoint) => [...toAmapLatLngTuple(point.lat, point.lng), point.heat_weight]),
    ...incidents.value.map((item) => [...toAmapLatLngTuple(item.lat, item.lng), item.severity === 'critical' ? 1 : 0.65]),
  ]
  if ((L as any).heatLayer && heatData.length) {
    try {
      ;(L as any).heatLayer(heatData, {
        radius: 30,
        blur: 24,
        gradient: { 0.25: '#2dd4bf', 0.5: '#facc15', 0.75: '#fb923c', 1: '#ef4444' },
      }).addTo(map)
    } catch {
      mapNotice.value = mapNotice.value || '热力图暂不可用，风险点位和事件点位已正常加载'
    }
  }

  riskRes.data.points.forEach((point: RiskPoint) => {
    const marker = L.circleMarker(toAmapLatLng(point.lat, point.lng), {
      radius: 10,
      color: colorMap[point.warning_color],
      fillColor: colorMap[point.warning_color],
      fillOpacity: 0.85,
      weight: 2,
    }).addTo(map)
    marker.bindPopup(`<strong>${point.name}</strong><br/>风险等级：${point.risk_level}<br/>最近安置点：${point.nearby_shelter.name}`)
    marker.on('click', () => {
      selected.value = point
      selectedIncident.value = null
    })
  })

  incidents.value.forEach((incident) => {
    const marker = L.circleMarker(toAmapLatLng(incident.lat, incident.lng), {
      radius: incident.type === 'sos' ? 13 : 9,
      color: '#fff',
      fillColor: incidentColor(incident),
      fillOpacity: 0.95,
      weight: 2,
    }).addTo(map)
    marker.bindPopup(`<strong>${incidentLabels[incident.type]}</strong><br/>${incident.description}<br/>状态：${incident.status}`)
    marker.on('click', () => {
      selectedIncident.value = incident
      selected.value = null
    })
  })
})
</script>

<template>
  <section class="map-page">
    <div ref="mapEl" class="risk-map" :class="{ 'no-tile-key': !amapAvailable }"></div>
    <div v-if="mapNotice" class="map-key-notice">{{ mapNotice }}</div>

    <aside class="map-legend">
      <strong>图例</strong>
      <span><i class="legend-dot red"></i>高风险 / SOS</span>
      <span><i class="legend-dot orange"></i>中风险 / 高优先事件</span>
      <span><i class="legend-dot yellow"></i>低风险 / 普通事件</span>
      <span><i class="legend-dot blue"></i>待观察</span>
    </aside>

    <aside class="map-stats">
      <strong>群众上报事件</strong>
      <div><span>总数</span><b>{{ stats.total }}</b></div>
      <div><span>SOS</span><b>{{ stats.sos }}</b></div>
      <div><span>待核实</span><b>{{ stats.pending }}</b></div>
      <div><span>处置中</span><b>{{ stats.responding }}</b></div>
    </aside>

    <aside v-if="selected" class="risk-drawer">
      <span :class="['risk-badge', selected.warning_color]">{{ iconMap[selected.warning_color] }}</span>
      <h1>{{ selected.name }}</h1>
      <p>{{ selected.scenic_area }} · {{ selected.district }}</p>
      <div class="metric-grid">
        <div><small>风险指数</small><strong>{{ selected.risk_level }}</strong></div>
        <div><small>风险分值</small><strong>{{ selected.risk_score }}</strong></div>
      </div>
      <p>{{ selected.action }}</p>
      <div class="shelter-box">
        <small>最近安置点</small>
        <strong>{{ selected.nearby_shelter.name }}</strong>
        <span>距离约 {{ selected.nearby_shelter.distance_km }} km · 容量约 {{ selected.nearby_shelter.capacity }} 人</span>
      </div>
      <button class="primary-button wide" @click="router.push(selected?.guide_target || '/app')">查看避险指引</button>
    </aside>

    <aside v-if="selectedIncident" class="risk-drawer incident-drawer">
      <span class="risk-badge red">{{ selectedIncident.type === 'sos' ? 'SOS' : '报' }}</span>
      <h1>{{ incidentLabels[selectedIncident.type] }}</h1>
      <p>{{ selectedIncident.scenic_area || selectedIncident.district }} · {{ selectedIncident.status }}</p>
      <div class="metric-grid">
        <div><small>严重程度</small><strong>{{ selectedIncident.severity }}</strong></div>
        <div><small>上报角色</small><strong>{{ selectedIncident.reporter_role }}</strong></div>
      </div>
      <p>{{ selectedIncident.description }}</p>
      <div v-if="selectedIncident.nearest_shelter" class="shelter-box">
        <small>推荐安置点</small>
        <strong>{{ selectedIncident.nearest_shelter.name }}</strong>
        <span>距离约 {{ selectedIncident.nearest_shelter.distance_km }} km · 容量约 {{ selectedIncident.nearest_shelter.capacity }} 人</span>
      </div>
      <button class="primary-button wide" @click="router.push('/app')">返回预警动态</button>
    </aside>
  </section>
</template>
