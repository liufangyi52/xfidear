import * as L from 'leaflet'

export const amapJsKey = import.meta.env.VITE_AMAP_JS_KEY || import.meta.env.VITE_AMAP_KEY || ''
export const amapAvailable = true

export const ZHANGJIAJIE_CENTER: [number, number] = [29.1171, 110.4792]
export const ZHANGJIAJIE_CITY_ZOOM = 10
export const ZHANGJIAJIE_BOUNDS: L.LatLngBoundsExpression = [
  [28.6, 109.7],
  [30.0, 111.3],
]

const amapSubdomains = ['1', '2', '3', '4']
let amapJsApiPromise: Promise<unknown> | null = null
let amapLocaApiPromise: Promise<unknown> | null = null

declare global {
  interface Window {
    AMap?: unknown
    Loca?: unknown
    _AMapSecurityConfig?: Record<string, string>
  }
}

function outOfChina(lat: number, lng: number) {
  return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271
}

function transformLat(x: number, y: number) {
  let ret = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x))
  ret += ((20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2) / 3
  ret += ((20 * Math.sin(y * Math.PI) + 40 * Math.sin((y / 3) * Math.PI)) * 2) / 3
  ret += ((160 * Math.sin((y / 12) * Math.PI) + 320 * Math.sin((y * Math.PI) / 30)) * 2) / 3
  return ret
}

function transformLng(x: number, y: number) {
  let ret = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x))
  ret += ((20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2) / 3
  ret += ((20 * Math.sin(x * Math.PI) + 40 * Math.sin((x / 3) * Math.PI)) * 2) / 3
  ret += ((150 * Math.sin((x / 12) * Math.PI) + 300 * Math.sin((x / 30) * Math.PI)) * 2) / 3
  return ret
}

export function wgs84ToGcj02(lat: number, lng: number): [number, number] {
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || outOfChina(lat, lng)) return [lat, lng]
  const a = 6378245.0
  const ee = 0.00669342162296594323
  let dLat = transformLat(lng - 105.0, lat - 35.0)
  let dLng = transformLng(lng - 105.0, lat - 35.0)
  const radLat = (lat / 180.0) * Math.PI
  let magic = Math.sin(radLat)
  magic = 1 - ee * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  dLat = (dLat * 180.0) / (((a * (1 - ee)) / (magic * sqrtMagic)) * Math.PI)
  dLng = (dLng * 180.0) / ((a / sqrtMagic) * Math.cos(radLat) * Math.PI)
  return [lat + dLat, lng + dLng]
}

export function toAmapLatLng(lat: number, lng: number) {
  const [gcjLat, gcjLng] = wgs84ToGcj02(Number(lat), Number(lng))
  return L.latLng(gcjLat, gcjLng)
}

export function toAmapLatLngTuple(lat: number, lng: number): [number, number] {
  const [gcjLat, gcjLng] = wgs84ToGcj02(Number(lat), Number(lng))
  return [gcjLat, gcjLng]
}

export const ZHANGJIAJIE_AMAP_CENTER = toAmapLatLngTuple(ZHANGJIAJIE_CENTER[0], ZHANGJIAJIE_CENTER[1])
export const ZHANGJIAJIE_AMAP_BOUNDS: L.LatLngBoundsExpression = [
  toAmapLatLngTuple(28.6, 109.7),
  toAmapLatLngTuple(30.0, 111.3),
]

export function ensureAmapJsApi() {
  if (typeof window === 'undefined' || !amapJsKey) return Promise.resolve(null)
  if (window.AMap) return Promise.resolve(window.AMap)
  if (amapJsApiPromise) return amapJsApiPromise

  amapJsApiPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-amap-js-api="true"]')
    if (existing) {
      existing.addEventListener('load', () => resolve(window.AMap || null), { once: true })
      existing.addEventListener('error', reject, { once: true })
      return
    }

    const script = document.createElement('script')
    script.dataset.amapJsApi = 'true'
    script.async = true
    script.src = `https://webapi.amap.com/maps?v=2.1Beta&key=${encodeURIComponent(amapJsKey)}&plugin=AMap.Scale,AMap.ToolBar,AMap.Geocoder,AMap.Weather,AMap.HeatMap,AMap.DistrictSearch`
    script.onload = () => resolve(window.AMap || null)
    script.onerror = () => reject(new Error('AMap JS API failed to load'))
    document.head.appendChild(script)
  })

  return amapJsApiPromise
}

export async function ensureAmapLocaApi() {
  if (typeof window === 'undefined' || !amapJsKey) return null
  const amap = await ensureAmapJsApi()
  if (!amap) return null
  if (window.Loca) return { AMap: window.AMap, Loca: window.Loca }
  if (amapLocaApiPromise) return amapLocaApiPromise

  amapLocaApiPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-amap-loca-api="true"]')
    if (existing) {
      existing.addEventListener('load', () => resolve(window.Loca ? { AMap: window.AMap, Loca: window.Loca } : null), { once: true })
      existing.addEventListener('error', reject, { once: true })
      return
    }

    const script = document.createElement('script')
    script.dataset.amapLocaApi = 'true'
    script.async = true
    script.src = `https://webapi.amap.com/loca?v=2.0.0&key=${encodeURIComponent(amapJsKey)}`
    script.onload = () => resolve(window.Loca ? { AMap: window.AMap, Loca: window.Loca } : null)
    script.onerror = () => reject(new Error('AMap Loca API failed to load'))
    document.head.appendChild(script)
  })

  return amapLocaApiPromise
}

function createAmapVectorLayer() {
  return L.tileLayer(
    'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=7&x={x}&y={y}&z={z}',
    {
      subdomains: amapSubdomains,
      maxZoom: 18,
      attribution: '地图底图 © 高德地图',
    },
  )
}

function createAmapSatelliteLayer(style: 6 | 8) {
  return L.tileLayer(`https://webst0{s}.is.autonavi.com/appmaptile?style=${style}&x={x}&y={y}&z={z}`, {
    subdomains: amapSubdomains,
    maxZoom: 18,
    attribution: '地图底图 © 高德地图',
  })
}

export function addAmapLayers(
  map: L.Map,
  options: {
    onFallback?: () => void
    onJsApiReady?: (amap: unknown) => void
    defaultLayer?: 'vector' | 'image'
    showLayerControl?: boolean
  } = {},
) {
  if (amapJsKey) {
    void ensureAmapJsApi()
      .then((amap) => {
        if (amap) options.onJsApiReady?.(amap)
      })
      .catch(() => options.onFallback?.())
  }

  const vectorGroup = L.layerGroup([createAmapVectorLayer()])
  const imageGroup = L.layerGroup([createAmapSatelliteLayer(6), createAmapSatelliteLayer(8)])

  if (options.defaultLayer === 'image') imageGroup.addTo(map)
  else vectorGroup.addTo(map)
  if (options.showLayerControl !== false) {
    L.control
    .layers(
      {
        高德矢量图: vectorGroup,
        高德影像图: imageGroup,
      },
      {},
      {
        collapsed: false,
        position: 'topright',
      },
    )
    .addTo(map)
  }

  return true
}
