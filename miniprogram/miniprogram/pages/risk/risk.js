const api = require('../../utils/request')

function riskLevelText(level) {
  const map = {
    critical: '极高风险',
    high: '高风险',
    medium: '中风险',
    low: '低风险',
    red: '红色',
    orange: '橙色',
    yellow: '黄色',
    blue: '蓝色'
  }
  return map[level] || level || '风险'
}

Page({
  data: {
    user: null,
    isTourist: false,
    center: { lat: 29.3472, lng: 110.5587 },
    weather: {},
    points: [],
    markers: [],
    mapReady: false,
    loading: false,
    loadError: ''
  },

  onReady() {
    this.setData({ mapReady: true }, () => {
      if (this.pendingMapData) {
        const pending = this.pendingMapData
        this.pendingMapData = null
        this.setData(pending)
      }
    })
  },

  onLoad() {
    const app = getApp()
    const session = app.loadSession()
    if (!session.token) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.setData({
      user: session.user,
      isTourist: session.user.role === 'tourist'
    })
  },

  onShow() {
    this.load()
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh())
  },

  async load() {
    if (this.data.loading) return
    this.setData({ loading: true })
    try {
      const result = await api.get('/api/risk/current')
      this.setData({ loadError: '' })
      this.applyRiskData(result)
    } catch (error) {
      this.setData({
        loadError: (error && error.detail) || '无法连接后端，请确认服务已启动后刷新',
        weather: {},
        points: [],
        markers: []
      })
    } finally {
      this.setData({ loading: false })
    }
  },

  applyRiskData(result) {
    const rawPoints = result.points || []
    const scenicPoints = rawPoints.filter((item) => item.scenic_area)
    const selectedPoints = this.data.isTourist && scenicPoints.length ? scenicPoints : rawPoints
    const points = selectedPoints.map((item) => ({
      ...item,
      risk_level_text: riskLevelText(item.risk_level)
    }))
    const markers = points.slice(0, 20).map((item, index) => ({
      id: index,
      latitude: item.lat,
      longitude: item.lng,
      title: item.name,
      width: 28,
      height: 28,
      callout: {
        content: `${item.name} ${item.risk_score}`,
        color: '#102522',
        fontSize: 12,
        borderRadius: 4,
        bgColor: '#ffffff',
        padding: 6,
        display: 'BYCLICK'
      }
    }))
    const mapData = {
      markers,
      center: points[0] ? { lat: points[0].lat, lng: points[0].lng } : this.data.center
    }
    this.setData({
      weather: result.weather || {},
      points: points.slice(0, 12)
    })
    if (!this.data.mapReady) {
      this.pendingMapData = mapData
      return
    }
    wx.nextTick(() => {
      this.setData(mapData)
    })
  },

  showPoint(event) {
    const point = this.data.points[event.currentTarget.dataset.index]
    this.showPointModal(point)
  },

  onMarkerTap(event) {
    const point = this.data.points[event.detail.markerId]
    this.showPointModal(point)
  },

  showPointModal(point) {
    if (!point) return
    const shelter = point.nearby_shelter && point.nearby_shelter.name ? point.nearby_shelter.name : '待确认'
    wx.showModal({
      title: point.name,
      content: `${point.risk_level_text}，评分 ${point.risk_score}。\n${point.action}\n最近安置点：${shelter}`,
      showCancel: false
    })
  }
})
