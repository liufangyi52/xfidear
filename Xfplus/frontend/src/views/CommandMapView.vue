<script setup lang="ts">
import * as L from 'leaflet'
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  BarChart3,
  BellRing,
  Bot,
  ClipboardList,
  Database,
  FileText,
  LogOut,
  MapPinned,
  Megaphone,
  Minus,
  Plus,
  RefreshCw,
  RotateCcw,
  Siren,
  Target,
  ThermometerSun,
} from 'lucide-vue-next'
import { api } from '../api'
import { clearSession, loadActiveScope, loadSession } from '../auth'
import { ensureLeafletHeat } from '../leafletHeat'
import {
  addAmapLayers,
  amapAvailable,
  ensureAmapLocaApi,
  toAmapLatLng,
  toAmapLatLngTuple,
  ZHANGJIAJIE_AMAP_BOUNDS,
  ZHANGJIAJIE_AMAP_CENTER,
  ZHANGJIAJIE_CENTER,
  ZHANGJIAJIE_CITY_ZOOM,
} from '../mapLayers'
import type { Incident } from '../types'

const router = useRouter()
const mapEl = ref<HTMLDivElement | null>(null)
const locaMapEl = ref<HTMLDivElement | null>(null)
const bigscreenRightPanelEl = ref<HTMLElement | null>(null)
const weatherChartEl = ref<HTMLDivElement | null>(null)
const eventChartEl = ref<HTMLDivElement | null>(null)
const districtChartEl = ref<HTMLDivElement | null>(null)
const riskTypeTrendDetailChartEl = ref<HTMLDivElement | null>(null)
const riskTypeDistrictDetailChartEl = ref<HTMLDivElement | null>(null)
const overview = ref<any>(null)
const selectedPoint = ref<any>(null)
const selectedIncident = ref<Incident | null>(null)
const notice = ref('')
const mapNotice = ref('')
const heatVisible = ref(true)
const smartEyeVisible = ref(localStorage.getItem('smart_eye_hidden') !== '1')
const weatherDetailOpen = ref(false)
// Added: bigscreen weather card state and realtime Beijing clock.
const bigscreenRiskTypeExpanded = ref(true)
const bigscreenWeatherExpanded = ref(true)
const bigscreenDistrictExpanded = ref(true)
const riskTypeDetailOpen = ref(false)
const clockNow = ref(Date.now())
const bigscreenMode = ref(true)
const BIGSCREEN_DRAWER_STORAGE_KEY = 'bigscreen_side_drawer_open'
const sideDrawerOpen = ref(localStorage.getItem(BIGSCREEN_DRAWER_STORAGE_KEY) !== '0')
type BigscreenPanel = 'capacity' | 'messages' | 'weather' | 'events' | 'districts'
const activeBigscreenPanel = ref<BigscreenPanel | null>(null)
const user = computed(() => loadSession())
const activeScope = computed(() => loadActiveScope())
type MapLayerKey = 'risk' | 'incidents' | 'shelters'

interface WeatherChartDay {
  label: string
  date: string
  low: number
  high: number
  humidity: number
  precipitation: number
}

type BigscreenWorkspaceKind = 'route' | 'demo' | 'refresh' | 'zoom'

interface BigscreenWorkspaceAction {
  id: string
  label: string
  desc: string
  icon: any
  kind: BigscreenWorkspaceKind
  path?: string
}

const mapLayerVisible = ref<Record<MapLayerKey, boolean>>({
  risk: true,
  incidents: true,
  shelters: true,
})

function currentDistrict() {
  return activeScope.value?.activeDistrict || user.value?.district
}

function currentCommunity() {
  return activeScope.value?.activeCommunity || user.value?.community
}

let map: L.Map | null = null
let heatLayer: any = null
let layerGroup: L.LayerGroup | null = null
let locaMap: any = null
let loca: any = null
let locaLayers: any[] = []
let locaMarkers: any[] = []
let locaSatelliteLayers: any[] = []
let locaBoundaryOverlays: any[] = []
let weatherChart: echarts.ECharts | null = null
let eventChart: echarts.ECharts | null = null
let districtChart: echarts.ECharts | null = null
let riskTypeTrendDetailChart: echarts.ECharts | null = null
let riskTypeDistrictDetailChart: echarts.ECharts | null = null
let clockTimer: ReturnType<typeof window.setInterval> | null = null
const commandDistricts = ['永定区', '武陵源区', '慈利县', '桑植县'] as const
const riskTypePalette = ['#ff5c7a', '#ffb84d', '#5bc8ff', '#30ffad', '#a78bfa', '#f472b6', '#94a3b8']

const workflowActions = computed(() => {
  const isCommunity = user.value?.role === 'community_admin'
  const actions = [
    {
      label: isCommunity ? '预警转发' : '预警发布',
      desc: isCommunity ? '转发上级预警到本社区' : '创建预警并推送站内消息',
      path: '/admin/alerts',
      icon: BellRing,
    },
    { label: '事件管理', desc: '核实、处置现场上报和 SOS', path: '/admin/incidents', icon: ClipboardList },
    { label: '消息管理', desc: '按角色和辖区下发通知', path: '/messages', icon: Megaphone },
    { label: '广播管理', desc: '查看推送与语音播报记录', path: '/admin/broadcasts', icon: BarChart3 },
    { label: '复盘报告', desc: '生成处置复盘与建议', path: '/admin/reports', icon: FileText },
  ]

  if (!isCommunity) {
    actions.push({ label: '风险数据', desc: '查看隐患点与安置点', path: '/risk-data', icon: Database })
  }

  return actions
})

const incidentLabels: Record<string, string> = {
  flood: '积水/山洪',
  landslide: '滑坡/落石',
  road: '道路中断',
  medical: '人员受伤',
  sos: 'SOS 求助',
  shelter: '安置需求',
  other: '其他事件',
}

const statusLabels: Record<string, string> = {
  pending: '待核实',
  responding: '处置中',
  resolved: '已完成',
}

const severityLabels: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '紧急',
}

const centers: Record<string, [number, number, number]> = {
  city_admin: [ZHANGJIAJIE_CENTER[0], ZHANGJIAJIE_CENTER[1], ZHANGJIAJIE_CITY_ZOOM],
  county_admin: [29.33, 110.55, 11],
  community_admin: [29.35, 110.55, 13],
}

const weather = computed(() => overview.value?.weather || {})
const currentMapScope = computed(() => currentCommunity() || currentDistrict() || '张家界市')
function formatWeatherDateToken(date?: string | null) {
  const source = String(date || '').trim()
  if (!source) return ''
  const match = source.match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})/)
  if (!match) return source
  return `${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}`
}

function formatWeatherDayLabel(weekLabel?: string | null, date?: string | null) {
  const label = String(weekLabel || '').trim()
  const dateToken = formatWeatherDateToken(date)
  if (!label) return dateToken || '未来'
  if (!dateToken) return label
  return `${dateToken}${label}`
}

function extractBeijingDateParts(value: string | number | Date | null | undefined) {
  const source = value instanceof Date ? value : new Date(value ?? '')
  if (Number.isNaN(source.getTime())) return null
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    weekday: 'long',
    hour12: false,
  }).formatToParts(source)
  const map = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return {
    year: map.year,
    month: map.month,
    day: map.day,
    hour: map.hour,
    minute: map.minute,
    second: map.second,
    weekday: map.weekday,
  }
}

function formatBeijingTimestamp(value: string | number | Date | null | undefined, includeWeekday = false) {
  const parts = extractBeijingDateParts(value)
  if (!parts) return typeof value === 'string' ? value : '--'
  const base = `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
  return includeWeekday ? `${base} | ${parts.weekday}` : base
}

const weatherForecastDays = computed(() => weather.value.forecast_days || [])
const weatherChartDays = computed<WeatherChartDay[]>(() => {
  const days = weatherForecastDays.value.length
    ? weatherForecastDays.value
    : [{
        date: weather.value.updated_at || '当前',
        week_label: '实时',
        temp_range: weather.value.temperature === undefined || weather.value.temperature === null ? '--' : `${weather.value.temperature}℃`,
        humidity: weather.value.humidity,
        precipitation: weather.value.rainfall_24h,
      }]

  return days.map((day: any, index: number) => {
    const rangeValues = String(day.temp_range || '')
      .match(/-?\d+(?:\.\d+)?/g)
      ?.map(Number)
      .filter((value) => Number.isFinite(value)) || []
    const low = rangeValues.length > 1 ? Math.min(...rangeValues) : Number(weather.value.temperature ?? rangeValues[0] ?? 0)
    const high = rangeValues.length > 1 ? Math.max(...rangeValues) : Number(weather.value.temperature ?? rangeValues[0] ?? low)
    const fallbackLabel = index === 0 ? '当前' : `第${index + 1}天`
    return {
      label: formatWeatherDayLabel(day.week_label || fallbackLabel, day.date),
      date: day.date || fallbackLabel,
      low,
      high,
      humidity: Number(day.humidity ?? weather.value.humidity ?? 0),
      precipitation: Number(day.precipitation ?? day.rainfall_24h ?? weather.value.rainfall_24h ?? 0),
    }
  })
})
const weatherTemperatureText = computed(() => {
  const temperature = weather.value.temperature
  return temperature === undefined || temperature === null ? '--℃' : `${Number(temperature).toFixed(1)}℃`
})
const weatherHumidityText = computed(() => {
  const humidity = weather.value.humidity
  return humidity === undefined || humidity === null ? '湿度 --' : `湿度 ${Number(humidity).toFixed(0)}%`
})
const weatherRainfallText = computed(() => {
  const rainfall = Number(weather.value.rainfall_24h ?? 0)
  return `降雨${weather.value.rainfall_estimated ? '估算' : ''} ${rainfall.toFixed(1)} mm`
})
const realtimeClockText = computed(() => formatBeijingTimestamp(clockNow.value, true))
const weatherUpdatedAtText = computed(() => formatBeijingTimestamp(weather.value.updated_at || weather.value.forecast_updated_at))
const weatherCardSummary = computed(() => `${weather.value.city || '张家界市'} · ${weather.value.text || weather.value.summary || '天气加载中'}`)
const weatherFooterNote = computed(
  () => `天气预报接口提供天气现象、温度和风力；降雨量为依据天气现象的风险估算值，实时温度来自实况接口。更新时间：${weatherUpdatedAtText.value || '--'}`,
)
const shelterCapacity = computed(() => (overview.value?.shelters || []).reduce((sum: number, item: any) => sum + Number(item.capacity || 0), 0))
const businessActions = computed(() => workflowActions.value)
const refreshActionState = ref<'idle' | 'refreshing' | 'done'>('idle')
let refreshActionStateTimer: ReturnType<typeof window.setTimeout> | null = null
const utilityBigscreenActions = computed<BigscreenWorkspaceAction[]>(() => [
  {
    id: 'refresh',
    label: refreshActionState.value === 'refreshing' ? '正在刷新' : refreshActionState.value === 'done' ? '刷新完成' : '刷新态势',
    desc:
      refreshActionState.value === 'refreshing'
        ? '正在同步预警和事件'
        : refreshActionState.value === 'done'
          ? '预警和事件已同步'
          : '同步预警和事件',
    icon: RefreshCw,
    kind: 'refresh',
  },
  { id: 'zoom', label: '缩放辖区', desc: '回到负责范围', icon: Target, kind: 'zoom' },
])
const businessWorkspaceActions = computed<BigscreenWorkspaceAction[]>(() =>
  businessActions.value.map((action) => ({
    id: action.path,
    label: action.label,
    desc: action.desc,
    icon: action.icon,
    kind: 'route' as const,
    path: action.path,
  })),
)
const bigscreenWorkspaceActions = computed<BigscreenWorkspaceAction[]>(() => [
  ...businessWorkspaceActions.value,
  ...utilityBigscreenActions.value,
])
const activeBigscreenWorkspaceActionId = ref<string | null>(null)
const activeBigscreenWorkspaceAction = computed(
  () => bigscreenWorkspaceActions.value.find((action) => action.id === activeBigscreenWorkspaceActionId.value) || null,
)
const visibleBigscreenWorkspaceActions = computed(() => bigscreenWorkspaceActions.value)
const routeWorkspaceOpen = computed(() => activeBigscreenWorkspaceAction.value?.kind === 'route')
const bigscreenWorkspaceFrameSrc = computed(() => {
  const action = activeBigscreenWorkspaceAction.value
  if (!action?.path) return ''
  return `${action.path}${action.path.includes('?') ? '&' : '?'}embedded=1`
})
const eventTypeStats = computed(() => {
  const mapData = new Map<string, number>()
  ;(overview.value?.incidents || []).forEach((incident: Incident) => {
    const label = incidentLabels[incident.type] || '其他事件'
    mapData.set(label, (mapData.get(label) || 0) + 1)
  })
  return Array.from(mapData.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
})
const riskTypeTotal = computed(() => eventTypeStats.value.reduce((sum, item) => sum + Number(item.value || 0), 0))
const riskTypeSummary = computed(() => {
  const top = eventTypeStats.value[0]
  if (!top) return '当前暂无风险事件'
  return `共 ${eventTypeStats.value.length} 类风险，最高为 ${top.name}`
})
const eventStatusStats = computed(() => {
  const mapData = new Map<string, number>()
  ;(overview.value?.incidents || []).forEach((incident: Incident) => {
    const label = statusLabels[incident.status] || incident.status || '未知状态'
    mapData.set(label, (mapData.get(label) || 0) + 1)
  })
  return Array.from(mapData.entries()).map(([name, value]) => ({ name, value }))
})
const districtIncidentStats = computed(() => {
  const mapData = new Map<string, number>(commandDistricts.map((district) => [district, 0]))
  ;(overview.value?.incidents || []).forEach((incident: Incident) => {
    const district = incident.district && mapData.has(incident.district) ? incident.district : '永定区'
    mapData.set(district, (mapData.get(district) || 0) + 1)
  })
  return commandDistricts.map((district) => ({ name: district, value: mapData.get(district) || 0 }))
})
const riskTypeDetailRows = computed(() => {
  const groups = new Map<string, {
    count: number
    latestTime: string | null
    districts: Set<string>
    latestIncidentTime: number
  }>()
  ;(overview.value?.incidents || []).forEach((incident: Incident) => {
    const name = incidentLabels[incident.type] || '其他事件'
    const district = incident.district || currentDistrict() || '张家界市'
    const createdAt = incident.created_at || ''
    const createdAtTime = createdAt ? new Date(createdAt).getTime() : Number.NaN
    if (!groups.has(name)) {
      groups.set(name, {
        count: 0,
        latestTime: null,
        districts: new Set<string>(),
        latestIncidentTime: Number.NaN,
      })
    }
    const current = groups.get(name)!
    current.count += 1
    current.districts.add(district)
    if (!Number.isNaN(createdAtTime) && (Number.isNaN(current.latestIncidentTime) || createdAtTime > current.latestIncidentTime)) {
      current.latestIncidentTime = createdAtTime
      current.latestTime = createdAt
    } else if (!current.latestTime && createdAt) {
      current.latestTime = createdAt
    }
  })
  const total = riskTypeTotal.value || 1
  return Array.from(groups.entries())
    .map(([name, item], index) => ({
      name,
      count: item.count,
      percent: ((item.count / total) * 100).toFixed(1),
      areas: Array.from(item.districts).slice(0, 3).join('、') || '暂无',
      latestTime: formatDateTime(item.latestTime),
      color: riskTypePalette[index % riskTypePalette.length],
    }))
    .sort((left, right) => right.count - left.count)
})
const riskTypeDetailSummary = computed(() => riskTypeDetailRows.value[0] || null)
const riskTypeLastEventTime = computed(() => {
  const latest = [...(overview.value?.incidents || [])]
    .map((incident: Incident) => incident.created_at)
    .filter(Boolean)
    .sort()
    .at(-1)
  return formatDateTime(latest)
})
const riskTypeActiveDistrictCount = computed(() =>
  districtIncidentStats.value.filter((item) => item.value > 0).length,
)
const riskTypeTrendData = computed(() => {
  const currentYear = new Date().getFullYear()
  const years = Array.from({ length: 10 }, (_, index) => {
    const year = currentYear - (9 - index)
    return {
      key: String(year),
      label: String(year),
    }
  })
  const trackedTypes = riskTypeDetailRows.value.length
    ? riskTypeDetailRows.value.map((item) => item.name)
    : ['积水/山洪', '道路中断', '滑坡/落石', 'SOS 求助']
  const byType = new Map<string, Map<string, number>>()
  trackedTypes.forEach((name) => byType.set(name, new Map<string, number>()))
  ;(overview.value?.incidents || []).forEach((incident: Incident) => {
    const name = incidentLabels[incident.type] || '其他事件'
    if (!byType.has(name)) return
    const date = new Date(incident.created_at || '')
    if (Number.isNaN(date.getTime())) return
    const key = String(date.getFullYear())
    const store = byType.get(name)!
    store.set(key, (store.get(key) || 0) + 1)
  })
  return {
    labels: years.map((item) => item.label),
    series: trackedTypes.map((name, index) => ({
      name,
      color: riskTypePalette[index % riskTypePalette.length],
      values: years.map((year) => byType.get(name)?.get(year.key) || 0),
    })),
  }
})
const riskTypeDistrictSeries = computed(() => {
  const trackedTypes = riskTypeDetailRows.value.length
    ? riskTypeDetailRows.value.map((item) => item.name)
    : ['积水/山洪', '道路中断', '滑坡/落石', 'SOS 求助']
  const base = new Map<string, Map<string, number>>()
  trackedTypes.forEach((name) => {
    const districtMap = new Map<string, number>()
    commandDistricts.forEach((district) => districtMap.set(district, 0))
    base.set(name, districtMap)
  })
  ;(overview.value?.incidents || []).forEach((incident: Incident) => {
    const name = incidentLabels[incident.type] || '其他事件'
    if (!base.has(name)) return
    const district = incident.district && commandDistricts.includes(incident.district as any) ? incident.district : commandDistricts[0]
    const districtMap = base.get(name)!
    districtMap.set(district, (districtMap.get(district) || 0) + 1)
  })
  return trackedTypes.map((name, index) => ({
    name,
    color: riskTypePalette[index % riskTypePalette.length],
    values: commandDistricts.map((district) => base.get(name)?.get(district) || 0),
  }))
})
const screenMessages = computed(() => overview.value?.messages || [])
const roleLabels: Record<string, string> = {
  city_admin: '市级',
  county_admin: '区县',
  community_admin: '社区',
  resident: '居民',
  tourist: '游客',
}
const messageStatusLabels: Record<string, string> = {
  sent: '已发送',
  pending: '待处理',
  reviewed: '已回复',
  forwarded: '已转办',
  resolved: '已完成',
}
const messageSourceLabels: Record<string, string> = {
  manual: '手动下发',
  alert_push: '预警推送',
  assistant_alert_push: 'AI 预警',
  public_suggestion: '公众建议',
  suggestion_reply: '建议回复',
  rectification_task: '整改任务',
  system: '系统消息',
}
const bigscreenPanelTitle = computed(() => {
  const titles: Record<BigscreenPanel, string> = {
    capacity: '安置容量',
    messages: '消息触达',
    weather: '天气',
    events: '事件统计',
    districts: '区县风险',
  }
  return activeBigscreenPanel.value ? titles[activeBigscreenPanel.value] : ''
})

const shelterMapIcon = L.divIcon({
  className: 'shelter-map-marker',
  html: '<span class="shelter-map-marker__roof"></span><span class="shelter-map-marker__body"></span>',
  iconSize: [34, 34],
  iconAnchor: [17, 17],
  popupAnchor: [0, -18],
})

function closeWorkbenchDrawer() {
  map?.closePopup()
  selectedPoint.value = null
  selectedIncident.value = null
  weatherDetailOpen.value = false
}

function selectRiskPoint(point: any) {
  map?.closePopup()
  selectedPoint.value = point
  selectedIncident.value = null
  weatherDetailOpen.value = false
}

function selectIncident(incident: Incident) {
  map?.closePopup()
  selectedIncident.value = incident
  selectedPoint.value = null
  weatherDetailOpen.value = false
}

function exitToPortal() {
  clearSession()
  router.push('/')
}

function formatDateTime(value?: string | null) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatMessageRoles(roles?: string[]) {
  if (!roles?.length) return '全部'
  return roles.map((role) => roleLabels[role] || role).join('、')
}

function formatMessageScope(message: any) {
  return [message.target_district, message.target_community].filter(Boolean).join(' / ') || '全域'
}

function chartAxisLabel(value: string) {
  const text = String(value || '')
  if (text.length <= 4) return text
  return text.match(/.{1,4}/g)?.join('\n') || text
}

function chartThemeOptions() {
  return {
    textStyle: { color: '#b8ffe3', fontFamily: 'Microsoft YaHei, sans-serif' },
    grid: { top: 36, right: 24, bottom: 34, left: 46, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(5, 24, 22, 0.92)',
      borderColor: 'rgba(48, 255, 173, 0.35)',
      textStyle: { color: '#eafff6' },
    },
    xAxis: {
      axisLine: { lineStyle: { color: 'rgba(91, 255, 196, 0.32)' } },
      axisLabel: { color: '#9eeed0', fontSize: 11, interval: 0, formatter: chartAxisLabel },
      splitLine: { show: false },
    },
    yAxis: {
      axisLine: { show: false },
      axisLabel: { color: '#9eeed0', fontSize: 11, margin: 10 },
      nameGap: 18,
      nameTextStyle: { color: '#9eeed0', fontSize: 11, padding: [0, 0, 0, 8] },
      splitLine: { lineStyle: { color: 'rgba(91, 255, 196, 0.12)' } },
    },
  }
}

function initCharts() {
  if (!bigscreenMode.value) return
  if (weatherChartEl.value && !weatherChart) weatherChart = echarts.init(weatherChartEl.value)
  if (eventChartEl.value && !eventChart) eventChart = echarts.init(eventChartEl.value)
  if (districtChartEl.value && !districtChart) districtChart = echarts.init(districtChartEl.value)
  updateCharts()
}

function initRiskTypeDetailCharts() {
  if (!bigscreenMode.value || !riskTypeDetailOpen.value) return
  if (riskTypeTrendDetailChartEl.value && !riskTypeTrendDetailChart) {
    riskTypeTrendDetailChart = echarts.init(riskTypeTrendDetailChartEl.value)
  }
  if (riskTypeDistrictDetailChartEl.value && !riskTypeDistrictDetailChart) {
    riskTypeDistrictDetailChart = echarts.init(riskTypeDistrictDetailChartEl.value)
  }
  updateRiskTypeDetailCharts()
}

function resetRightPanelScroll() {
  if (!bigscreenMode.value) return
  if (bigscreenRightPanelEl.value) bigscreenRightPanelEl.value.scrollTop = 0
}

function updateCharts() {
  if (!bigscreenMode.value) return
  const theme = chartThemeOptions()

  const weatherDays = weatherChartDays.value
  const weatherChartWidth = weatherChartEl.value?.clientWidth ?? 0
  const weatherChartHeight = weatherChartEl.value?.clientHeight ?? 0
  const compactWeatherChart = (weatherChartWidth > 0 && weatherChartWidth <= 420) || (weatherChartHeight > 0 && weatherChartHeight <= 300)
  const weatherCardWidth = compactWeatherChart ? 72 : 146
  const weatherCardGap = compactWeatherChart ? 78 : 158
  const weatherLegendTop = compactWeatherChart ? 74 : 86
  const weatherGridTop = compactWeatherChart ? 104 : 124
  const weatherGridBottom = compactWeatherChart ? 44 : 34
  const weatherNowCards = [
    { label: '实时温度', value: weatherTemperatureText.value, color: '#8de7ff' },
    { label: '实时湿度', value: weatherHumidityText.value.replace('湿度 ', ''), color: '#30ffad' },
    { label: '降雨量', value: weatherRainfallText.value.replace('降雨估算 ', '').replace('降雨 ', ''), color: '#60f0ff' },
    { label: '当前天气', value: weather.value.text || weather.value.summary || '--', color: '#ffcf5a' },
  ]
  weatherChart?.setOption({
    ...theme,
    legend: {
      top: weatherLegendTop,
      left: 8,
      textStyle: { color: '#d3f1ff', fontSize: compactWeatherChart ? 8 : 10, fontWeight: 700 },
      itemWidth: compactWeatherChart ? 7 : 9,
      itemHeight: compactWeatherChart ? 5 : 6,
    },
    graphic: [
      {
        type: 'group',
        left: compactWeatherChart ? 4 : 8,
        top: compactWeatherChart ? 4 : 8,
        children: weatherNowCards.flatMap((card, index) => {
          const x = index * weatherCardGap
          return [
            {
              type: 'rect',
              x,
              y: 0,
              shape: { width: weatherCardWidth, height: compactWeatherChart ? 44 : 58, r: 8 },
              style: {
                fill: 'rgba(25, 89, 142, .42)',
                stroke: 'rgba(137, 222, 255, .32)',
                lineWidth: 1,
                shadowBlur: 14,
                shadowColor: 'rgba(58, 171, 255, .16)',
              },
            },
            {
              type: 'text',
              x: x + (compactWeatherChart ? 8 : 12),
              y: compactWeatherChart ? 10 : 13,
              style: {
                text: card.label,
                fill: 'rgba(211, 241, 255, .72)',
                font: compactWeatherChart ? '700 8px sans-serif' : '700 11px sans-serif',
              },
            },
            {
              type: 'text',
              x: x + (compactWeatherChart ? 8 : 12),
              y: compactWeatherChart ? 26 : 34,
              style: {
                text: String(card.value),
                fill: card.color,
                font: compactWeatherChart ? '900 11px sans-serif' : '900 17px sans-serif',
              },
            },
          ]
        }),
      },
      {
        type: 'text',
        right: 10,
        bottom: 4,
        style: {
          text: weatherFooterNote.value,
          fill: 'rgba(211, 241, 255, .5)',
          font: compactWeatherChart ? '700 8px sans-serif' : '700 10px sans-serif',
          width: compactWeatherChart ? Math.max(weatherChartWidth - 20, 250) : undefined,
          overflow: compactWeatherChart ? 'break' : undefined,
          lineHeight: compactWeatherChart ? 11 : undefined,
        },
      },
    ],
    grid: {
      top: weatherGridTop,
      right: compactWeatherChart ? 16 : 30,
      bottom: weatherGridBottom,
      left: compactWeatherChart ? 16 : 30,
      containLabel: true,
    },
    tooltip: {
      ...theme.tooltip,
      trigger: 'axis',
      formatter(params: any[]) {
        const first = params?.[0]
        const item = weatherDays[first?.dataIndex || 0]
        const lines = params.map((param) => `${param.marker}${param.seriesName}：${param.value}${param.seriesName === '降雨' ? ' mm' : param.seriesName === '湿度' ? '%' : '℃'}`)
        return [`${item?.date || first?.axisValue || ''}`, ...lines].join('<br/>')
      },
    },
    xAxis: {
      ...theme.xAxis,
      type: 'category',
      data: weatherDays.map((item) => item.label),
      axisLabel: {
        color: '#9eeed0',
        fontSize: compactWeatherChart ? 8 : 10,
        interval: 0,
        formatter(value: string) {
          return value.replace(' ', '\n')
        },
      },
    },
    yAxis: [
      { ...theme.yAxis, type: 'value', name: '', axisLabel: { color: '#9eeed0', fontSize: compactWeatherChart ? 8 : 10 } },
      {
        ...theme.yAxis,
        type: 'value',
        name: '',
        axisLabel: { color: '#9eeed0', fontSize: compactWeatherChart ? 8 : 10, formatter: '{value}' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '最高温',
        type: 'line',
        smooth: true,
        symbolSize: compactWeatherChart ? 4 : 6,
        data: weatherDays.map((item) => item.high),
        lineStyle: { width: 3, color: '#ffcf5a' },
        itemStyle: { color: '#ffcf5a' },
        areaStyle: { color: 'rgba(255, 207, 90, .12)' },
      },
      {
        name: '最低温',
        type: 'line',
        smooth: true,
        symbolSize: compactWeatherChart ? 4 : 6,
        data: weatherDays.map((item) => item.low),
        lineStyle: { width: 3, color: '#5bc8ff' },
        itemStyle: { color: '#5bc8ff' },
      },
      {
        name: '降雨',
        type: 'bar',
        yAxisIndex: 1,
        data: weatherDays.map((item) => item.precipitation),
        barWidth: compactWeatherChart ? 8 : 12,
        itemStyle: {
          borderRadius: [8, 8, 0, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#60f0ff' },
            { offset: 1, color: 'rgba(96, 240, 255, .22)' },
          ]),
        },
      },
      {
        name: '湿度',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbolSize: compactWeatherChart ? 4 : 5,
        data: weatherDays.map((item) => item.humidity),
        lineStyle: { width: 2, type: 'dashed', color: '#30ffad' },
        itemStyle: { color: '#30ffad' },
      },
    ],
  })

  const eventTypes = eventTypeStats.value
  const riskChartWidth = eventChartEl.value?.clientWidth ?? 0
  const compactRiskChart = riskChartWidth > 0 && riskChartWidth <= 340
  const riskLegendWidth = compactRiskChart ? 92 : 112
  const riskCenterX = compactRiskChart ? '34%' : '36%'
  eventChart?.setOption({
    ...theme,
    tooltip: {
      ...theme.tooltip,
      trigger: 'item',
      formatter: '{b}<br/>{c} 件 ({d}%)',
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 0,
      top: 8,
      bottom: 8,
      width: riskLegendWidth,
      itemGap: compactRiskChart ? 10 : 14,
      icon: 'roundRect',
      itemWidth: compactRiskChart ? 10 : 12,
      itemHeight: compactRiskChart ? 8 : 10,
      textStyle: { color: '#d3f1ff', fontSize: compactRiskChart ? 10 : 11, fontWeight: 700 },
      pageIconColor: '#8de7ff',
      pageTextStyle: { color: '#d3f1ff' },
    },
    xAxis: undefined,
    yAxis: undefined,
    grid: undefined,
    graphic: [
      {
        type: 'group',
        left: riskCenterX,
        top: '50%',
        bounding: 'raw',
        children: [
          {
            type: 'text',
            left: -38,
            top: -24,
            style: {
              text: '风险总量',
              fill: 'rgba(211, 241, 255, .72)',
              font: compactRiskChart ? '700 11px sans-serif' : '700 12px sans-serif',
            },
          },
          {
            type: 'text',
            left: -22,
            top: -2,
            style: {
              text: `${riskTypeTotal.value}`,
              fill: '#8de7ff',
              font: compactRiskChart ? '1000 24px sans-serif' : '1000 28px sans-serif',
            },
          },
          {
            type: 'text',
            left: -14,
            top: 28,
            style: {
              text: '件',
              fill: 'rgba(211, 241, 255, .72)',
              font: compactRiskChart ? '700 10px sans-serif' : '700 11px sans-serif',
            },
          },
        ],
      },
    ],
    series: [
      {
        name: '风险类型',
        type: 'pie',
        radius: compactRiskChart ? ['42%', '68%'] : ['40%', '68%'],
        center: [riskCenterX, '52%'],
        minAngle: 8,
        avoidLabelOverlap: true,
        data: eventTypes.length ? eventTypes : [{ name: '暂无事件', value: 0 }],
        label: { show: false },
        labelLine: { show: false },
        itemStyle: { borderColor: 'rgba(4, 18, 34, .8)', borderWidth: 2 },
        color: ['#ff5c7a', '#ffb84d', '#5bc8ff', '#30ffad', '#a78bfa', '#f472b6', '#94a3b8'],
      },
    ],
  })

  const districts = districtIncidentStats.value
  districtChart?.setOption({
    ...theme,
    grid: { top: 24, right: 12, bottom: 28, left: 30, containLabel: true },
    tooltip: {
      ...theme.tooltip,
      trigger: 'axis',
      formatter(params: any[]) {
        const item = params?.[0]
        return `${item?.axisValue || ''}<br/>危机事件 ${item?.value ?? 0} 件`
      },
    },
    xAxis: {
      ...theme.xAxis,
      type: 'category',
      data: districts.map((item) => item.name),
      axisLabel: { color: '#9eeed0', fontSize: 10, interval: 0, formatter: chartAxisLabel },
    },
    yAxis: { ...theme.yAxis, type: 'value', axisLabel: { color: '#9eeed0', fontSize: 10 } },
    series: [{
      name: '危机事件',
      type: 'bar',
      data: districts.map((item) => item.value),
      barWidth: 22,
      itemStyle: {
        borderRadius: [8, 8, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#ff7b7b' },
          { offset: 1, color: '#5bc8ff' },
        ]),
      },
      label: { show: true, position: 'top', distance: 6, color: '#eafff6', fontSize: 10 },
    }],
  })
}

function updateRiskTypeDetailCharts() {
  if (!bigscreenMode.value || !riskTypeDetailOpen.value) return
  const theme = chartThemeOptions()
  riskTypeTrendDetailChart?.setOption({
    ...theme,
    legend: {
      top: 6,
      left: 6,
      textStyle: { color: '#d3f1ff', fontSize: 11, fontWeight: 700 },
      itemWidth: 10,
      itemHeight: 6,
    },
    grid: { top: 44, right: 20, bottom: 28, left: 36, containLabel: true },
    tooltip: {
      ...theme.tooltip,
      trigger: 'axis',
    },
    xAxis: {
      ...theme.xAxis,
      type: 'category',
      data: riskTypeTrendData.value.labels,
      axisLabel: { color: '#9eeed0', fontSize: 10, interval: 0 },
    },
    yAxis: {
      ...theme.yAxis,
      type: 'value',
      axisLabel: { color: '#9eeed0', fontSize: 10 },
    },
    series: riskTypeTrendData.value.series.map((item) => ({
      name: item.name,
      type: 'line',
      smooth: true,
      symbolSize: 6,
      data: item.values,
      lineStyle: { width: 3, color: item.color },
      itemStyle: { color: item.color },
      areaStyle: { color: `${item.color}22` },
    })),
  })

  riskTypeDistrictDetailChart?.setOption({
    ...theme,
    legend: {
      top: 6,
      left: 6,
      textStyle: { color: '#d3f1ff', fontSize: 11, fontWeight: 700 },
      itemWidth: 10,
      itemHeight: 6,
    },
    grid: { top: 44, right: 16, bottom: 28, left: 36, containLabel: true },
    tooltip: {
      ...theme.tooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    xAxis: {
      ...theme.xAxis,
      type: 'category',
      data: [...commandDistricts],
      axisLabel: { color: '#9eeed0', fontSize: 10, interval: 0, formatter: chartAxisLabel },
    },
    yAxis: {
      ...theme.yAxis,
      type: 'value',
      axisLabel: { color: '#9eeed0', fontSize: 10 },
    },
    series: riskTypeDistrictSeries.value.map((item) => ({
      name: item.name,
      type: 'bar',
      data: item.values,
      barMaxWidth: 18,
      itemStyle: {
        borderRadius: [8, 8, 0, 0],
        color: item.color,
      },
    })),
  })
}

function resizeCharts() {
  weatherChart?.resize()
  eventChart?.resize()
  districtChart?.resize()
  riskTypeTrendDetailChart?.resize()
  riskTypeDistrictDetailChart?.resize()
  resizeLocaMap()
}

function disposeCharts() {
  weatherChart?.dispose()
  weatherChart = null
  eventChart?.dispose()
  eventChart = null
  districtChart?.dispose()
  districtChart = null
  riskTypeTrendDetailChart?.dispose()
  riskTypeTrendDetailChart = null
  riskTypeDistrictDetailChart?.dispose()
  riskTypeDistrictDetailChart = null
}

function disposeOverlayCharts() {
  eventChart?.dispose()
  eventChart = null
}

function incidentColor(incident: Incident) {
  if (incident.severity === 'critical') return '#dc2626'
  if (incident.severity === 'high') return '#f97316'
  if (incident.severity === 'medium') return '#eab308'
  return '#14b8a6'
}

function heatSpotColor(weight: number) {
  if (weight >= 0.95) return '#dc2626'
  if (weight >= 0.72) return '#f97316'
  return '#facc15'
}

function heatSpotIcon(weight: number) {
  const color = heatSpotColor(weight)
  const size = Math.round(58 + Math.min(weight, 1.35) * 34)
  const delay = `${(weight % 0.7).toFixed(2)}s`
  return L.divIcon({
    className: 'workbench-heat-pulse-marker',
    html: `
      <span class="workbench-heat-pulse" style="--heat-color:${color};--heat-delay:${delay};">
        <i></i><b></b>
      </span>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  })
}

function normalizedHeatPoints() {
  return [...(overview.value?.heat_points || []), ...(overview.value?.incident_heat_points || [])]
    .map((point: any) => {
      const lat = Number(point[0])
      const lng = Number(point[1])
      const rawWeight = Number(point[2] ?? 0.65)
      const weight = Number.isFinite(rawWeight) ? Math.max(0.35, Math.min(rawWeight, 1.35)) : 0.65
      return { lat, lng, weight }
    })
    .filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lng) && point.lat && point.lng)
}

async function loadOverview() {
  overview.value = (
    await api.get('/api/command/overview', {
      params: {
        time_range: 'all',
        active_district: currentDistrict(),
        active_community: currentCommunity(),
      },
    })
  ).data
  nextTick(() => updateCharts())
}

function centerForScope() {
  const points = overview.value?.risk_points || overview.value?.incidents || []
  if (points.length) {
    const lat = points.reduce((sum: number, point: any) => sum + Number(point.lat || 0), 0) / points.length
    const lng = points.reduce((sum: number, point: any) => sum + Number(point.lng || 0), 0) / points.length
    if (Number.isFinite(lat) && Number.isFinite(lng) && lat && lng) {
      return [lat, lng, user.value?.role === 'community_admin' ? 13 : 11] as [number, number, number]
    }
  }
  return centers[user.value?.role || 'city_admin'] || centers.city_admin
}

function toAmapLngLat(lat: number, lng: number): [number, number] {
  const [gcjLat, gcjLng] = toAmapLatLngTuple(Number(lat), Number(lng))
  return [gcjLng, gcjLat]
}

function geoJsonSource(Loca: any, features: any[]) {
  return new Loca.GeoJSONSource({
    data: {
      type: 'FeatureCollection',
      features,
    },
  })
}

function pointFeature(item: any, properties: Record<string, any> = {}) {
  return {
    type: 'Feature',
    geometry: {
      type: 'Point',
      coordinates: toAmapLngLat(Number(item.lat), Number(item.lng)),
    },
    properties: {
      ...properties,
      id: item.id,
      name: item.name || item.description,
      capacity: Number(item.capacity || 0),
      riskScore: Number(item.risk_score || 0),
      severity: item.severity,
      warningColor: item.warning_color,
      type: item.type,
    },
  }
}

function clearLocaLayers() {
  locaLayers.forEach((layer) => {
    try {
      layer.remove?.()
    } catch {
      try {
        loca?.remove?.(layer)
      } catch {
        // Ignore Loca cleanup differences between API builds.
      }
    }
  })
  locaLayers = []
  locaMarkers.forEach((marker) => {
    try {
      marker.setMap?.(null)
    } catch {
      // Ignore stale marker handles.
    }
  })
  locaMarkers = []
}

function addLocaLayer(layer: any) {
  if (!layer) return
  locaLayers.push(layer)
  try {
    loca?.add?.(layer)
  } catch {
    // Some Loca layer constructors bind to the container directly.
  }
}

function addLocaClickMarker(item: any, kind: 'risk' | 'incident' | 'shelter') {
  const AMap = (window as any).AMap
  if (!AMap || !locaMap || !Number.isFinite(Number(item.lat)) || !Number.isFinite(Number(item.lng))) return
  const marker = new AMap.Marker({
    position: toAmapLngLat(Number(item.lat), Number(item.lng)),
    anchor: 'center',
    zIndex: 280,
    content: '<span class="loca-click-hotspot"></span>',
  })
  marker.on('click', () => {
    if (kind === 'risk') selectRiskPoint(item)
    if (kind === 'incident') selectIncident(item)
  })
  marker.setMap(locaMap)
  locaMarkers.push(marker)
}

function applyLocaBaseLayer() {
  if (!locaMap) return
  const useSatellite = false
  try {
    locaMap.setMapStyle(useSatellite ? 'amap://styles/dark' : 'amap://styles/darkblue')
  } catch {
    // Style changes are optional when a loaded JS API build does not support custom styles.
  }
  locaSatelliteLayers.forEach((layer) => {
    try {
      layer.setMap(useSatellite ? locaMap : null)
    } catch {
      // Ignore optional satellite layer failures.
    }
  })
}

function renderLocaLayers() {
  if (!locaMap || !loca || !overview.value) return
  const Loca = (window as any).Loca
  if (!Loca) return
  clearLocaLayers()

  const heatFeatures = normalizedHeatPoints().map((point) => pointFeature(point, { weight: point.weight }))
  if (heatVisible.value && heatFeatures.length && Loca.PointLayer) {
    const heat = new Loca.PointLayer({ zIndex: 80, blend: 'lighter' })
    heat.setSource(geoJsonSource(Loca, heatFeatures))
    heat.setStyle({
      unit: 'px',
      radius: (_index: number, feature: any) => 18 + Number(feature.properties.weight || 0) * 42,
      color: 'rgba(34, 211, 238, 0.30)',
      borderWidth: 0,
      blurRadius: 18,
    })
    addLocaLayer(heat)
  }

  if (mapLayerVisible.value.risk && Loca.PrismLayer) {
    const riskFeatures = (overview.value.risk_points || []).map((point: any) => pointFeature(point, { category: 'risk' }))
    if (riskFeatures.length) {
      const riskLayer = new Loca.PrismLayer({ zIndex: 120, opacity: 1, visible: true, hasSide: true })
      riskLayer.setSource(geoJsonSource(Loca, riskFeatures))
      riskLayer.setStyle({
        unit: 'meter',
        radius: 140,
        sideNumber: 4,
        height: (_index: number, feature: any) => 420 + Math.min(Number(feature.properties.riskScore || 0) * 9, 780),
        topColor: '#ffd27a',
        sideTopColor: '#ff9f1a',
        sideBottomColor: 'rgba(255, 77, 79, 0.14)',
      })
      addLocaLayer(riskLayer)
    }
    ;(overview.value.risk_points || []).forEach((point: any) => addLocaClickMarker(point, 'risk'))
  }

  if (mapLayerVisible.value.shelters && Loca.PrismLayer) {
    const shelterFeatures = (overview.value.shelters || []).map((shelter: any) => pointFeature(shelter, { category: 'shelter' }))
    if (shelterFeatures.length) {
      const shelterLayer = new Loca.PrismLayer({ zIndex: 130, opacity: 0.92, visible: true, hasSide: true })
      shelterLayer.setSource(geoJsonSource(Loca, shelterFeatures))
      shelterLayer.setStyle({
        unit: 'meter',
        radius: 120,
        sideNumber: 32,
        height: (_index: number, feature: any) => 260 + Math.min(Number(feature.properties.capacity || 0) * 0.72, 900),
        topColor: '#9efff0',
        sideTopColor: '#31f7d4',
        sideBottomColor: 'rgba(40, 199, 255, 0.12)',
      })
      addLocaLayer(shelterLayer)
    }
    ;(overview.value.shelters || []).forEach((shelter: any) => addLocaClickMarker(shelter, 'shelter'))
  }

  if (mapLayerVisible.value.incidents && Loca.PointLayer) {
    const incidentFeatures = ((overview.value.incidents || []) as Incident[])
      .filter((incident) => incident.status === 'pending')
      .map((incident) => pointFeature(incident, { category: 'incident' }))
    if (incidentFeatures.length) {
      const incidentLayer = new Loca.PointLayer({ zIndex: 180, blend: 'lighter' })
      incidentLayer.setSource(geoJsonSource(Loca, incidentFeatures))
      incidentLayer.setStyle({
        unit: 'px',
        radius: (_index: number, feature: any) => feature.properties.type === 'sos' ? 28 : 20,
        color: (_index: number, feature: any) => feature.properties.severity === 'critical' || feature.properties.type === 'sos'
          ? 'rgba(255, 77, 79, 0.95)'
          : 'rgba(255, 207, 64, 0.88)',
        borderWidth: 3,
        borderColor: 'rgba(255, 255, 255, 0.8)',
      })
      try {
        incidentLayer.addAnimate({
          key: 'radius',
          value: [0.7, 1.65],
          duration: 900,
          easing: 'Linear',
          yoyo: true,
          repeat: 9999,
        })
      } catch {
        // Animation is visual sugar; the point layer remains interactive without it.
      }
      addLocaLayer(incidentLayer)
    }
    ;((overview.value.incidents || []) as Incident[])
      .filter((incident) => incident.status === 'pending')
      .forEach((incident) => addLocaClickMarker(incident, 'incident'))
  }

  try {
    loca.animate?.start?.()
  } catch {
    // Ignore optional animation startup failures.
  }
}

function renderLayers() {
  if (!map || !overview.value) return

  layerGroup?.clearLayers()
  if (heatLayer) {
    map.removeLayer(heatLayer)
    heatLayer = null
  }
  layerGroup = L.layerGroup().addTo(map)

  const heatData = normalizedHeatPoints().map((point) => [...toAmapLatLngTuple(point.lat, point.lng), point.weight])
  if ((L as any).heatLayer && heatData.length) {
    try {
      heatLayer = (L as any).heatLayer(heatData, {
        radius: 54,
        blur: 32,
        maxZoom: 13,
        minOpacity: 0.42,
        gradient: { 0.12: '#22d3ee', 0.34: '#facc15', 0.62: '#fb923c', 0.86: '#ef4444', 1: '#991b1b' },
      })
      if (heatVisible.value) heatLayer.addTo(map)
    } catch {
      heatLayer = null
      mapNotice.value = mapNotice.value || '热力图暂不可用，风险点位和事件点位已正常加载'
    }
  }

  if (heatVisible.value) {
    normalizedHeatPoints().forEach((point) => {
      L.marker(toAmapLatLng(point.lat, point.lng), {
        icon: heatSpotIcon(point.weight),
        interactive: false,
        keyboard: false,
      }).addTo(layerGroup as L.LayerGroup)
    })
  }

  if (mapLayerVisible.value.risk) {
    ;(overview.value.risk_points || []).forEach((point: any) => {
    const palette: Record<string, string> = { red: '#ef4444', orange: '#f97316', yellow: '#eab308', blue: '#3b82f6' }
    const color = palette[point.warning_color] || '#3b82f6'
    const marker = L.circleMarker(toAmapLatLng(point.lat, point.lng), {
      radius: 11,
      color: '#ffffff',
      fillColor: color,
      fillOpacity: 0.96,
      weight: 3,
      className: 'glow-marker',
    }).addTo(layerGroup as L.LayerGroup)
    marker.on('click', () => selectRiskPoint(point))
    })
  }

  if (mapLayerVisible.value.incidents) {
    ;((overview.value.incidents || []).filter((item: Incident) => item.status === 'pending')).forEach((incident: Incident) => {
    const marker = L.circleMarker(toAmapLatLng(incident.lat, incident.lng), {
      radius: incident.type === 'sos' ? 14 : 11,
      color: '#ffffff',
      fillColor: incidentColor(incident),
      fillOpacity: 0.96,
      weight: 3,
      className: incident.type === 'sos' ? 'glow-marker sos-marker' : 'glow-marker',
    }).addTo(layerGroup as L.LayerGroup)
    marker.on('click', () => selectIncident(incident))
    })
  }

  if (mapLayerVisible.value.shelters) {
    ;(overview.value.shelters || []).forEach((shelter: any) => {
      L.marker(toAmapLatLng(shelter.lat, shelter.lng), { icon: shelterMapIcon })
        .addTo(layerGroup as L.LayerGroup)
        .bindPopup(`<strong>${shelter.name}</strong><br/>容量：${shelter.capacity} 人`)
    })
  }
}

async function initMap() {
  if (!mapEl.value) return
  const center = centerForScope()

  if (map) {
    try {
      map.remove()
    } catch {
      // Ignore map teardown differences during mode switches.
    }
    map = null
    layerGroup = null
    heatLayer = null
  }

  map = L.map(mapEl.value, {
    zoomControl: true,
    scrollWheelZoom: 'center',
    doubleClickZoom: true,
    dragging: true,
    touchZoom: true,
    maxBounds: ZHANGJIAJIE_AMAP_BOUNDS,
    maxBoundsViscosity: 0.7,
  }).setView(toAmapLatLngTuple(center[0], center[1]), center[2])
  if (!addAmapLayers(map, {
    onFallback: () => {
      mapNotice.value = '高德地图加载失败，已保留业务点位图层'
    },
    defaultLayer: bigscreenMode.value ? 'image' : 'vector',
    showLayerControl: false,
  })) {
    mapNotice.value = '未配置高德地图 Key，已启用默认底图，业务点位仍可正常查看'
  }
  renderLayers()
  nextTick(() => map?.invalidateSize())
}

async function initLocaMap() {
  if (!locaMapEl.value || locaMap) {
    renderLocaLayers()
    return
  }
  try {
    const bundle = await ensureAmapLocaApi()
    const AMap = (bundle as any)?.AMap || (window as any).AMap
    const Loca = (bundle as any)?.Loca || (window as any).Loca
    if (!AMap || !Loca) {
      mapNotice.value = mapNotice.value || '高德 Loca 暂不可用，已保留常规地图业务图层'
      return
    }
    const center = centerForScope()
    const satellite = new AMap.TileLayer.Satellite({ opacity: 0.72, visible: false })
    const roadNet = new AMap.TileLayer.RoadNet({ opacity: 0.62, visible: false })
    locaSatelliteLayers = [satellite, roadNet]
    locaMap = new AMap.Map(locaMapEl.value, {
      center: toAmapLngLat(center[0], center[1]),
      zoom: center[2] + 0.4,
      zooms: [9, 17],
      pitch: 58,
      rotation: -18,
      viewMode: '3D',
      terrain: true,
      mapStyle: 'amap://styles/darkblue',
      showLabel: true,
      features: ['bg', 'road', 'point'],
      dragEnable: true,
      zoomEnable: true,
      rotateEnable: true,
      pitchEnable: true,
      scrollWheel: true,
      doubleClickZoom: true,
    })
    lockLocaToZhangjiajie(AMap)
    renderZhangjiajieBoundary(AMap)
    loca = new Loca.Container({ map: locaMap })
    applyLocaBaseLayer()
    locaMap.on?.('complete', () => {
      renderLocaLayers()
      locaMap.resize?.()
    })
    renderLocaLayers()
    setTimeout(() => locaMap?.resize?.(), 80)
  } catch {
    mapNotice.value = mapNotice.value || '高德 Loca 2.5D 地图加载失败，已保留常规地图业务图层'
  }
}

function resizeLocaMap() {
  try {
    locaMap?.resize?.()
  } catch {
    // Ignore resize failures while the 2.5D map is hidden.
  }
}

function lockLocaToZhangjiajie(AMap: any) {
  if (!AMap || !locaMap) return
  try {
    const bounds = new AMap.Bounds(
      new AMap.LngLat((ZHANGJIAJIE_AMAP_BOUNDS as [number, number][])[0][1], (ZHANGJIAJIE_AMAP_BOUNDS as [number, number][])[0][0]),
      new AMap.LngLat((ZHANGJIAJIE_AMAP_BOUNDS as [number, number][])[1][1], (ZHANGJIAJIE_AMAP_BOUNDS as [number, number][])[1][0]),
    )
    locaMap.setLimitBounds?.(bounds)
  } catch {
    // Limit bounds are a progressive enhancement for the 2.5D map.
  }
}

function renderZhangjiajieBoundary(AMap: any) {
  if (!AMap || !locaMap || !AMap.DistrictSearch) return
  try {
    locaBoundaryOverlays.forEach((overlay) => overlay.setMap?.(null))
    locaBoundaryOverlays = []
    const districtSearch = new AMap.DistrictSearch({
      extensions: 'all',
      subdistrict: 0,
      level: 'city',
    })
    districtSearch.search('430800', (_status: string, result: any) => {
      const boundaries = result?.districtList?.[0]?.boundaries || []
      if (!boundaries.length) return
      try {
        locaMap.setMask?.(boundaries)
      } catch {
        // Mask support varies by AMap build; boundary lines still keep the city scope clear.
      }
      boundaries.forEach((path: any) => {
        const polygon = new AMap.Polygon({
          path,
          zIndex: 80,
          fillColor: 'rgba(3, 18, 18, 0.08)',
          fillOpacity: 0.08,
          strokeColor: '#30ffad',
          strokeOpacity: 0.82,
          strokeWeight: 2,
          strokeStyle: 'solid',
        })
        polygon.setMap(locaMap)
        locaBoundaryOverlays.push(polygon)
      })
    })
  } catch {
    // The fixed Zhangjiajie bounds still prevent the 2.5D map from drifting away.
  }
}

function zoomToScope() {
  const center = centerForScope()
  map?.setView(toAmapLatLngTuple(center[0], center[1]), center[2])
  locaMap?.setZoomAndCenter?.(center[2] + 0.4, toAmapLngLat(center[0], center[1]))
  locaMap?.setPitch?.(58)
  locaMap?.setRotation?.(-18)
}

function resetZhangjiajie() {
  map?.setView(ZHANGJIAJIE_AMAP_CENTER, ZHANGJIAJIE_CITY_ZOOM)
  locaMap?.setZoomAndCenter?.(ZHANGJIAJIE_CITY_ZOOM + 0.4, [ZHANGJIAJIE_AMAP_CENTER[1], ZHANGJIAJIE_AMAP_CENTER[0]])
  locaMap?.setPitch?.(58)
  locaMap?.setRotation?.(-18)
}

function adjustMapZoom(step: 1 | -1) {
  if (!map) return
  const center = map.getCenter()
  const nextZoom = map.getZoom() + step
  map.setView(center, nextZoom)
  locaMap?.setZoomAndCenter?.(nextZoom + 0.4, toAmapLngLat(center.lat, center.lng))
  locaMap?.setPitch?.(58)
  locaMap?.setRotation?.(-18)
}

async function refreshWorkbench() {
  if (refreshActionStateTimer) {
    window.clearTimeout(refreshActionStateTimer)
    refreshActionStateTimer = null
  }
  refreshActionState.value = 'refreshing'
  notice.value = '正在刷新工作台态势...'
  try {
    await loadOverview()
    renderLayers()
    renderLocaLayers()
    updateCharts()
    map?.invalidateSize()
    resizeLocaMap()
    notice.value = '工作台态势已刷新'
    refreshActionState.value = 'done'
    refreshActionStateTimer = window.setTimeout(() => {
      refreshActionState.value = 'idle'
      refreshActionStateTimer = null
    }, 2200)
  } catch (error) {
    refreshActionState.value = 'idle'
    throw error
  }
}

async function demoMode() {
  notice.value = '正在生成演示事件...'
  await api.post('/api/incidents/demo')
  await refreshWorkbench()
  notice.value = '演示事件已生成，工作台地图已刷新。'
}

function toggleHeat() {
  heatVisible.value = !heatVisible.value
  renderLayers()
  renderLocaLayers()
}

function syncSmartEyeState(event?: Event) {
  const nextVisible = typeof (event as CustomEvent<boolean> | undefined)?.detail === 'boolean'
    ? Boolean((event as CustomEvent<boolean>).detail)
    : localStorage.getItem('smart_eye_hidden') !== '1'
  smartEyeVisible.value = nextVisible
}

function toggleSmartEye() {
  const action = smartEyeVisible.value ? 'hide' : 'show'
  window.dispatchEvent(new CustomEvent('smart-eye-visibility', { detail: action }))
}

function closeBigscreenWorkspace() {
  activeBigscreenWorkspaceActionId.value = null
}

function handleEmbeddedWorkspaceMessage(event: MessageEvent<{ type?: string }>) {
  if (event.origin !== window.location.origin) return
  if (event.data?.type !== 'xfplus:close-bigscreen-workspace') return
  closeBigscreenWorkspace()
}

function toggleBigscreenWorkspace(action: BigscreenWorkspaceAction) {
  closeWorkbenchDrawer()
  activeBigscreenWorkspaceActionId.value = activeBigscreenWorkspaceActionId.value === action.id ? null : action.id
}

async function runBigscreenWorkspaceAction() {
  const action = activeBigscreenWorkspaceAction.value
  if (!action) return
  if (action.kind === 'demo') {
    await demoMode()
    closeBigscreenWorkspace()
    return
  }
  if (action.kind === 'refresh') {
    await refreshWorkbench()
    closeBigscreenWorkspace()
    return
  }
  if (action.kind === 'zoom') {
    zoomToScope()
    closeBigscreenWorkspace()
  }
}

async function handleBigscreenWorkspaceAction(action: BigscreenWorkspaceAction) {
  if (action.kind === 'route') {
    toggleBigscreenWorkspace(action)
    return
  }

  if (action.kind === 'refresh') {
    if (refreshActionState.value === 'refreshing') return
    await refreshWorkbench()
    return
  }

  if (action.kind === 'zoom') {
    zoomToScope()
    return
  }

  if (activeBigscreenWorkspaceActionId.value === action.id) {
    closeBigscreenWorkspace()
    return
  }

  activeBigscreenWorkspaceActionId.value = action.id
  await runBigscreenWorkspaceAction()
}

function closeBigscreenPanel() {
  disposeOverlayCharts()
  activeBigscreenPanel.value = null
  nextTick(() => resizeCharts())
}

function openRiskTypeDetail() {
  bigscreenRiskTypeExpanded.value = true
  riskTypeDetailOpen.value = true
  nextTick(() => {
    initRiskTypeDetailCharts()
    resizeCharts()
  })
}

function closeRiskTypeDetail() {
  riskTypeDetailOpen.value = false
  nextTick(() => resizeCharts())
}

function syncSideDrawerLayout() {
  localStorage.setItem(BIGSCREEN_DRAWER_STORAGE_KEY, sideDrawerOpen.value ? '1' : '0')
  nextTick(() => {
    map?.invalidateSize()
    resizeCharts()
    window.setTimeout(() => {
      map?.invalidateSize()
      resizeCharts()
    }, 320)
  })
}

function toggleSideDrawer() {
  sideDrawerOpen.value = !sideDrawerOpen.value
  syncSideDrawerLayout()
}

function toggleRiskTypeDetail() {
  if (riskTypeDetailOpen.value) {
    closeRiskTypeDetail()
    return
  }
  openRiskTypeDetail()
}

function toggleWeatherCardCollapsed() {
  bigscreenWeatherExpanded.value = !bigscreenWeatherExpanded.value
  if (bigscreenWeatherExpanded.value) {
    nextTick(() => {
      initCharts()
      resizeCharts()
    })
  }
}

function toggleRiskTypeCardCollapsed() {
  bigscreenRiskTypeExpanded.value = !bigscreenRiskTypeExpanded.value
  if (bigscreenRiskTypeExpanded.value) {
    nextTick(() => {
      initCharts()
      resizeCharts()
    })
  }
}

function toggleDistrictCardCollapsed() {
  bigscreenDistrictExpanded.value = !bigscreenDistrictExpanded.value
  if (bigscreenDistrictExpanded.value) {
    nextTick(() => {
      initCharts()
      resizeCharts()
    })
  }
}

onMounted(async () => {
  document.body.classList.toggle('command-bigscreen-active', bigscreenMode.value)
  window.addEventListener('resize', resizeCharts)
  window.addEventListener('message', handleEmbeddedWorkspaceMessage as EventListener)
  window.addEventListener('smart-eye-state', syncSmartEyeState as EventListener)
  syncSmartEyeState()
  clockTimer = window.setInterval(() => {
    clockNow.value = Date.now()
  }, 1000)
  await ensureLeafletHeat()
  try {
    await loadOverview()
  } catch {
    overview.value = { stats: {}, weather: {}, heat_points: [], incident_heat_points: [], risk_points: [], incidents: [], shelters: [], messages: [] }
    notice.value = '业务数据暂未加载，地图底图已先行显示'
  }
  await initMap()
  if (bigscreenMode.value) {
    await initLocaMap()
    nextTick(() => {
      resetRightPanelScroll()
      initCharts()
      resizeCharts()
    })
  }
})

watch(bigscreenMode, (enabled) => {
  document.body.classList.toggle('command-bigscreen-active', enabled)
  if (!enabled) closeBigscreenWorkspace()
  nextTick(async () => {
    await initMap()
    if (enabled) {
      resetRightPanelScroll()
      initCharts()
      void initLocaMap()
      resizeLocaMap()
    } else {
      disposeCharts()
    }
    map?.invalidateSize()
    updateCharts()
  })
})

watch(
  [eventTypeStats, eventStatusStats, districtIncidentStats, weatherChartDays, weatherTemperatureText, weatherHumidityText, weatherRainfallText, () => weather.value.text, weatherUpdatedAtText],
  () => {
    nextTick(() => updateCharts())
  },
)

watch([riskTypeDetailRows, riskTypeTrendData, riskTypeDistrictSeries], () => {
  if (!riskTypeDetailOpen.value) return
  nextTick(() => updateRiskTypeDetailCharts())
})

watch(riskTypeDetailOpen, (opened) => {
  if (!opened) return
  nextTick(() => {
    initRiskTypeDetailCharts()
    resizeCharts()
  })
})

watch(bigscreenRiskTypeExpanded, (expanded) => {
  if (!bigscreenMode.value || !expanded) return
  nextTick(() => updateCharts())
})

watch(bigscreenWeatherExpanded, (expanded) => {
  if (!bigscreenMode.value || !expanded) return
  nextTick(() => updateCharts())
})

watch(bigscreenDistrictExpanded, (expanded) => {
  if (!bigscreenMode.value || !expanded) return
  nextTick(() => updateCharts())
})

onBeforeUnmount(() => {
  document.body.classList.remove('command-bigscreen-active')
  window.removeEventListener('resize', resizeCharts)
  window.removeEventListener('message', handleEmbeddedWorkspaceMessage as EventListener)
  window.removeEventListener('smart-eye-state', syncSmartEyeState as EventListener)
  if (refreshActionStateTimer) window.clearTimeout(refreshActionStateTimer)
  if (clockTimer) window.clearInterval(clockTimer)
  disposeCharts()
  clearLocaLayers()
  locaSatelliteLayers.forEach((layer) => layer.setMap?.(null))
  try {
    loca?.destroy?.()
    locaMap?.destroy?.()
  } catch {
    // Ignore teardown differences between AMap builds.
  }
  map?.remove()
})
</script>

<template>
  <section class="workbench-screen workbench-neo is-bigscreen" :class="{ 'drawer-collapsed': !sideDrawerOpen, 'risk-detail-open': riskTypeDetailOpen }">
    <header v-if="!routeWorkspaceOpen" class="bigscreen-topbar">
      <div class="bigscreen-brand">
        <span>张家界 · 智瞳应急指挥平台</span>
        <div class="bigscreen-topbar-actions">
          <div class="bigscreen-live-time">{{ realtimeClockText }}</div>
          <button type="button" class="bigscreen-exit-button" @click="exitToPortal">
            <LogOut :size="15" />
            <em>退出</em>
          </button>
        </div>
      </div>
    </header>

    <div class="workbench-main bigscreen-main">
      <aside v-if="!routeWorkspaceOpen" class="bigscreen-left-drawer" :class="{ collapsed: !sideDrawerOpen }" aria-label="大屏功能抽屉">
        <button
          type="button"
          class="drawer-toggle"
          :aria-label="sideDrawerOpen ? '收起左侧功能按钮组' : '展开左侧功能按钮组'"
          :title="sideDrawerOpen ? '收起左侧功能按钮组' : '展开左侧功能按钮组'"
          @click="toggleSideDrawer"
        >
          <span class="drawer-toggle__icon">{{ sideDrawerOpen ? '◀' : '▶' }}</span>
          <span class="drawer-toggle__label">{{ sideDrawerOpen ? '收起菜单' : '展开菜单' }}</span>
        </button>
        <div class="drawer-content">
          <h2>业务功能</h2>
          <button
            v-for="action in visibleBigscreenWorkspaceActions"
            :key="action.id"
            type="button"
            class="bigscreen-action"
            :title="action.label"
            :class="[
              {
                active: activeBigscreenWorkspaceActionId === action.id,
                'is-refreshing': action.id === 'refresh' && refreshActionState === 'refreshing',
                'is-complete': action.id === 'refresh' && refreshActionState === 'done',
              },
              action.kind === 'demo' ? 'warning' : '',
            ]"
            :disabled="action.id === 'refresh' && refreshActionState === 'refreshing'"
            @click="handleBigscreenWorkspaceAction(action)"
          >
            <component :is="action.icon" :size="18" />
            <span>
              <strong>{{ action.label }}</strong>
              <small>{{ action.desc }}</small>
            </span>
          </button>
          <div class="drawer-divider"></div>
          <h2>测试快捷</h2>
          <button v-if="false" type="button" class="bigscreen-action warning" @click="demoMode">
            <Siren :size="18" /><span><strong>一键演示</strong><small>生成本地化事件</small></span>
          </button>
          <button v-if="false" type="button" class="bigscreen-action" @click="refreshWorkbench">
            <RefreshCw :size="18" /><span><strong>刷新态势</strong><small>同步预警和事件</small></span>
          </button>
          <button v-if="false" type="button" class="bigscreen-action" @click="zoomToScope">
            <Target :size="18" /><span><strong>缩放辖区</strong><small>回到负责范围</small></span>
          </button>
        </div>
      </aside>

      <section class="workbench-map-stage" aria-label="态势地图">
        <div class="map-orbit"></div>
        <div class="map-scan-ring"></div>
        <div class="workbench-map-card">
          <div ref="mapEl" class="workbench-map" :class="{ 'no-tile-key': !amapAvailable }"></div>
          <p v-if="mapNotice" class="map-key-notice command-map-notice">{{ mapNotice }}</p>
          <div class="map-toolbox" aria-label="地图工具">
            <button type="button" title="复位张家界" @click="resetZhangjiajie">
              <RotateCcw :size="16" />
              <span>复位</span>
            </button>
            <button type="button" title="定位辖区" @click="zoomToScope">
              <MapPinned :size="16" />
              <span>辖区</span>
            </button>
            <button type="button" :title="heatVisible ? '关闭热力图' : '打开热力图'" @click="toggleHeat">
              <ThermometerSun :size="16" />
              <span>{{ heatVisible ? '热力开' : '热力关' }}</span>
            </button>
            <button type="button" :title="smartEyeVisible ? '关闭智瞳' : '打开智瞳'" @click="toggleSmartEye">
              <Bot :size="16" />
              <span>{{ smartEyeVisible ? '智瞳关' : '智瞳开' }}</span>
            </button>
            <button type="button" class="map-toolbox-zoom" title="放大地图" aria-label="放大地图" @click="adjustMapZoom(1)">
              <Plus :size="14" />
            </button>
            <button type="button" class="map-toolbox-zoom" title="缩小地图" aria-label="缩小地图" @click="adjustMapZoom(-1)">
              <Minus :size="14" />
            </button>
          </div>
          <div class="map-scope-label">{{ currentMapScope }}</div>
          <button class="heat-toggle" @click="toggleHeat">
            <ThermometerSun :size="16" />热力图{{ heatVisible ? '开' : '关' }}
          </button>
          <button class="scope-button" @click="zoomToScope">
            <Target :size="16" />缩放辖区
          </button>

          <div v-if="selectedPoint || selectedIncident || weatherDetailOpen" class="workbench-detail-layer">
            <button type="button" class="workbench-drawer-backdrop" aria-label="关闭详情浮层" @click="closeWorkbenchDrawer"></button>

            <div v-if="selectedPoint" class="workbench-drawer" @click.stop>
              <button type="button" class="workbench-drawer-close" aria-label="关闭详情" @click="closeWorkbenchDrawer">×</button>
              <h3>{{ selectedPoint.name }}</h3>
              <p>{{ selectedPoint.district }} · {{ selectedPoint.scenic_area }}</p>
              <div class="screen-row"><span>风险等级</span><strong>{{ selectedPoint.risk_level }}</strong></div>
              <div class="screen-row"><span>风险分值</span><strong>{{ selectedPoint.risk_score }}</strong></div>
              <p>{{ selectedPoint.action }}</p>
              <small>
                最近安置点：{{ selectedPoint.nearby_shelter?.name || '待确认' }}，约
                {{ selectedPoint.nearby_shelter?.distance_km ?? '--' }} km
              </small>
            </div>

            <div v-if="selectedIncident" class="workbench-drawer" @click.stop>
              <button type="button" class="workbench-drawer-close" aria-label="关闭详情" @click="closeWorkbenchDrawer">×</button>
              <h3>{{ incidentLabels[selectedIncident.type] }} · {{ statusLabels[selectedIncident.status] }}</h3>
              <p>
                {{ selectedIncident.scenic_area || selectedIncident.district || '位置待确认' }}
                · {{ severityLabels[selectedIncident.severity] || selectedIncident.severity }}
              </p>
              <p>{{ selectedIncident.description }}</p>
              <small v-if="selectedIncident.need_review">游客上报：需管理员审核</small>
              <small v-if="selectedIncident.nearest_shelter">
                推荐安置点：{{ selectedIncident.nearest_shelter.name }}，约
                {{ selectedIncident.nearest_shelter.distance_km }} km
              </small>
            </div>

            <div v-if="weatherDetailOpen" class="workbench-drawer weather-detail-drawer" @click.stop>
              <button type="button" class="workbench-drawer-close" aria-label="关闭天气详情" @click="closeWorkbenchDrawer">×</button>
              <h3>{{ weather.city || '张家界市' }} · 未来天气</h3>
              <p>{{ weather.summary || weather.text || '天气数据加载中' }}</p>
              <div class="weather-now-grid">
                <div><span>实时温度</span><strong>{{ weatherTemperatureText }}</strong></div>
                <div><span>实时湿度</span><strong>{{ weatherHumidityText.replace('湿度 ', '') }}</strong></div>
                <div><span>当前天气</span><strong>{{ weather.text || '--' }}</strong></div>
                <div><span>降雨量</span><strong>{{ weatherRainfallText.replace('降雨估算 ', '').replace('降雨 ', '') }}</strong></div>
                <div><span>风向</span><strong>{{ weather.wind_direction || '--' }}</strong></div>
                <div><span>风力</span><strong>{{ weather.wind_power || '--' }}</strong></div>
              </div>
              <div class="weather-forecast-list">
                <article v-for="day in weatherForecastDays" :key="`${day.date}-${day.week_label}`" class="weather-forecast-card">
                  <div>
                    <span>{{ day.week_label || '未来' }}</span>
                    <strong>{{ day.date || '--' }}</strong>
                  </div>
                  <p>白天 {{ day.day_weather || '--' }} · 夜间 {{ day.night_weather || '--' }}</p>
                  <small>温度 {{ day.temp_range || '--' }} · 白天 {{ day.day_wind || '--' }} {{ day.day_power || '--' }} · 夜间 {{ day.night_wind || '--' }} {{ day.night_power || '--' }}</small>
                  <small>湿度 {{ day.humidity === undefined || day.humidity === null ? '暂无' : `${Number(day.humidity).toFixed(0)}%` }} · 降雨{{ day.rainfall_estimated ? '估算' : '' }} {{ Number(day.precipitation ?? 0).toFixed(1) }} mm</small>
                </article>
                <p v-if="!weatherForecastDays.length" class="weather-data-note">暂无未来天气预报，正在等待高德天气接口返回。</p>
              </div>
              <small class="weather-data-note">
                {{ weather.data_note || '天气数据来自高德地图天气 API。' }}
                更新时间：{{ weather.updated_at || weather.forecast_updated_at || '--' }}
              </small>
            </div>
          </div>

          <section
            v-if="routeWorkspaceOpen"
            class="bigscreen-workspace-overlay"
            :aria-label="`${activeBigscreenWorkspaceAction?.label || 'workspace'}-overlay`"
          >
            <div class="bigscreen-workspace-shell">
              <iframe
                :key="bigscreenWorkspaceFrameSrc"
                :src="bigscreenWorkspaceFrameSrc"
                :title="activeBigscreenWorkspaceAction?.label || 'bigscreen-workspace'"
                class="bigscreen-workspace-frame"
              ></iframe>
            </div>
          </section>

        </div>
      </section>

      <aside
        v-show="!riskTypeDetailOpen"
        ref="bigscreenRightPanelEl"
        class="bigscreen-right-panel"
        :class="{ 'is-risk-detail-open': riskTypeDetailOpen }"
        aria-label="大屏态势指标"
      >
        <section
          class="weather-fixed-panel risk-type-fixed-panel"
          :class="{
            'is-collapsed': !bigscreenRiskTypeExpanded && !riskTypeDetailOpen,
            'is-detail-trigger': riskTypeDetailOpen,
          }"
          aria-label="风险类型卡片"
        >
          <div class="weather-fixed-panel-head">
            <div class="weather-fixed-panel-copy">
              <strong>风险类型</strong>
              <span>{{ riskTypeDetailOpen ? '风险类型详情已展开' : riskTypeSummary }}</span>
            </div>
            <div class="weather-fixed-panel-actions">
              <button type="button" class="weather-fixed-action-button" @click="toggleRiskTypeDetail">
                {{ riskTypeDetailOpen ? '关闭详情' : '查看详情' }}
              </button>
              <small>{{ riskTypeTotal }} 件</small>
              <button type="button" class="weather-fixed-toggle" :aria-label="bigscreenRiskTypeExpanded ? '收起风险类型卡片' : '展开风险类型卡片'" @click="toggleRiskTypeCardCollapsed">
                {{ bigscreenRiskTypeExpanded ? '收' : '展' }}
              </button>
            </div>
          </div>
          <div v-show="!riskTypeDetailOpen" class="weather-fixed-panel-body risk-type-fixed-panel-body">
            <div ref="eventChartEl" class="screen-chart incident-donut-chart risk-type-fixed-chart"></div>
          </div>
        </section>

        <section
          v-show="!riskTypeDetailOpen"
          class="weather-fixed-panel weather-primary-panel"
          :class="{ 'is-collapsed': !bigscreenWeatherExpanded }"
          aria-label="天气态势卡片"
        >
          <div class="weather-fixed-panel-head">
            <div class="weather-fixed-panel-copy">
              <strong>天气态势</strong>
              <span>{{ weatherCardSummary }}</span>
            </div>
            <div class="weather-fixed-panel-actions">
              <small>{{ weatherUpdatedAtText || '--' }}</small>
              <button type="button" class="weather-fixed-toggle" :aria-label="bigscreenWeatherExpanded ? '收起天气态势卡片' : '展开天气态势卡片'" @click="toggleWeatherCardCollapsed">
                {{ bigscreenWeatherExpanded ? '收' : '展' }}
              </button>
            </div>
          </div>
          <div class="weather-fixed-panel-body">
            <div ref="weatherChartEl" class="screen-chart weather-trend-chart weather-fixed-chart"></div>
          </div>
        </section>
        <section
          v-show="!riskTypeDetailOpen"
          class="weather-fixed-panel district-fixed-panel"
          :class="{ 'is-collapsed': !bigscreenDistrictExpanded }"
          aria-label="区县风险卡片"
        >
          <div class="weather-fixed-panel-head">
            <div class="weather-fixed-panel-copy">
              <strong>区县风险</strong>
              <span>区县事件风险统计</span>
            </div>
            <div class="weather-fixed-panel-actions">
              <small>{{ districtIncidentStats.length }} 区县</small>
              <button type="button" class="weather-fixed-toggle" :aria-label="bigscreenDistrictExpanded ? '收起区县风险卡片' : '展开区县风险卡片'" @click="toggleDistrictCardCollapsed">
                {{ bigscreenDistrictExpanded ? '收' : '展' }}
              </button>
            </div>
          </div>
          <div class="weather-fixed-panel-body district-fixed-panel-body">
            <div ref="districtChartEl" class="screen-chart district-risk-chart district-fixed-chart"></div>
          </div>
        </section>
      </aside>
    </div>

    <transition name="bigscreen-risk-detail-fade">
      <section
        v-if="riskTypeDetailOpen"
        class="bigscreen-risk-detail-layer"
        aria-label="风险类型详情"
      >
        <button
          type="button"
          class="bigscreen-risk-detail-backdrop"
          aria-label="关闭风险类型详情"
          @click="closeRiskTypeDetail"
        ></button>
        <article class="bigscreen-risk-detail-modal" @click.stop>
          <header class="bigscreen-risk-detail-head">
            <div class="bigscreen-risk-detail-title">
              <strong>风险类型详细态势</strong>
              <span>
                {{ riskTypeDetailSummary?.name || '暂无重点风险' }}
                · {{ riskTypeDetailSummary?.count || 0 }} 件
                · 最近更新 {{ riskTypeLastEventTime }}
              </span>
            </div>
            <button type="button" class="bigscreen-risk-detail-close" aria-label="关闭风险类型详情" @click="closeRiskTypeDetail">×</button>
          </header>

          <div class="bigscreen-risk-detail-metrics">
            <span>
              <small>风险类型数</small>
              <strong>{{ riskTypeDetailRows.length }}</strong>
            </span>
            <span>
              <small>风险事件总量</small>
              <strong>{{ riskTypeTotal }}</strong>
            </span>
            <span>
              <small>最高风险类型</small>
              <strong>{{ riskTypeDetailSummary?.name || '暂无' }}</strong>
            </span>
            <span>
              <small>高风险区县数</small>
              <strong>{{ riskTypeActiveDistrictCount }}</strong>
            </span>
          </div>

          <div class="bigscreen-risk-detail-grid">
            <section class="bigscreen-risk-detail-card">
              <div class="bigscreen-risk-detail-card-head">
                <strong>风险类型明细统计</strong>
                <span>事件数 / 占比 / 主要区域 / 最近发生时间</span>
              </div>
              <div class="bigscreen-table-wrap">
                <table class="bigscreen-data-table risk-type-detail-table">
                  <thead>
                    <tr>
                      <th>风险类型</th>
                      <th>事件数</th>
                      <th>占比</th>
                      <th>主要区域</th>
                      <th>最近发生时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in riskTypeDetailRows" :key="item.name">
                      <td>
                        <span class="risk-type-table-tag" :style="{ '--risk-type-accent': item.color }">
                          {{ item.name }}
                        </span>
                      </td>
                      <td>{{ item.count }} 件</td>
                      <td>{{ item.percent }}%</td>
                      <td>{{ item.areas }}</td>
                      <td>{{ item.latestTime }}</td>
                    </tr>
                    <tr v-if="!riskTypeDetailRows.length">
                      <td colspan="5" class="empty-table-cell">暂无风险类型明细</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section class="bigscreen-risk-detail-card">
              <div class="bigscreen-risk-detail-card-head">
                <strong>近 10 年风险趋势分析</strong>
                <span>按风险类型展示年度事件量</span>
              </div>
              <div ref="riskTypeTrendDetailChartEl" class="screen-chart bigscreen-risk-detail-chart"></div>
            </section>

            <section class="bigscreen-risk-detail-card">
              <div class="bigscreen-risk-detail-card-head">
                <strong>高风险区域分布</strong>
                <span>各区县风险类型对比</span>
              </div>
              <div ref="riskTypeDistrictDetailChartEl" class="screen-chart bigscreen-risk-detail-chart"></div>
            </section>
          </div>
        </article>
      </section>
    </transition>

    <section
      v-if="activeBigscreenPanel && activeBigscreenPanel !== 'weather' && activeBigscreenPanel !== 'districts'"
      class="bigscreen-glass-modal"
      :class="{
        'is-capacity-panel': activeBigscreenPanel === 'capacity',
      }"
      aria-live="polite"
    >
      <header v-if="activeBigscreenPanel !== 'capacity'" class="bigscreen-modal-header">
        <h2>{{ bigscreenPanelTitle }}</h2>
        <button type="button" aria-label="关闭弹窗" @click="closeBigscreenPanel">×</button>
      </header>

      <button
        v-if="activeBigscreenPanel === 'capacity'"
        type="button"
        class="bigscreen-floating-close"
        aria-label="关闭弹窗"
        @click="closeBigscreenPanel"
      >
        ×
      </button>

      <div v-if="activeBigscreenPanel === 'capacity'" class="bigscreen-modal-body capacity-panel">
        <div class="capacity-orb">
          <strong>{{ shelterCapacity }}</strong>
          <span>总容纳人数</span>
        </div>
        <div class="event-summary-list shelter-list">
          <span v-for="shelter in (overview?.shelters || []).slice(0, 8)" :key="shelter.id || shelter.name">
            {{ shelter.name }} <b>{{ shelter.capacity || 0 }}人</b>
          </span>
          <span v-if="!(overview?.shelters || []).length">暂无安置点 <b>0</b></span>
        </div>
      </div>

      <div v-else-if="activeBigscreenPanel === 'messages'" class="bigscreen-modal-body">
        <div class="bigscreen-table-wrap">
          <table class="bigscreen-data-table message-data-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>标题</th>
                <th>内容</th>
                <th>来源</th>
                <th>对象</th>
                <th>区域</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="message in screenMessages" :key="message.id">
                <td>{{ formatDateTime(message.created_at) }}</td>
                <td>{{ message.title || '--' }}</td>
                <td class="table-text-cell">{{ message.content || '--' }}</td>
                <td>{{ messageSourceLabels[message.source_type || ''] || message.source_type || '消息' }}</td>
                <td>{{ formatMessageRoles(message.target_roles) }}</td>
                <td>{{ formatMessageScope(message) }}</td>
                <td>{{ messageStatusLabels[message.status || ''] || message.status || '--' }}</td>
              </tr>
              <tr v-if="!screenMessages.length">
                <td colspan="7" class="empty-table-cell">暂无消息</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else-if="activeBigscreenPanel === 'events'" class="bigscreen-modal-body visual-panel events-visual-panel">
        <div class="event-summary-list">
          <span v-for="item in eventTypeStats" :key="item.name">{{ item.name }} <b>{{ item.value }} 件</b></span>
          <span v-if="!eventTypeStats.length">暂无事件 <b>0 件</b></span>
        </div>
      </div>

    </section>

    <p class="workbench-source-note">
      天气数据优先由高德地图天气 API 提供，地图底图使用高德地图 API，地质灾害点信息根据政府公开资料整理。
      安置点容量采用官方公开转移人数或按场地类型估算，比赛可上线运行版不替代政府正式应急系统。
      © 2026 张家界·智瞳应急平台
    </p>
  </section>
</template>
