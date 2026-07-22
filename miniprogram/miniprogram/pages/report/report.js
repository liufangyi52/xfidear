const api = require('../../utils/request')
const { isBackendSession } = require('../../utils/session')
const { currentDistrict, inferDistrictFromText, saveScope } = require('../../utils/location_scope')

const EVENT_TYPES = [
  {
    key: 'other',
    label: '自动识别',
    template: '现场发现积水、落石、道路受阻或人员滞留等情况，请求现场核实并协助处置。'
  },
  {
    key: 'flood',
    label: '积水山洪',
    template: '现场出现积水或山洪风险，水位上涨，低洼路段通行困难，请安排巡查、警戒和疏导。'
  },
  {
    key: 'landslide',
    label: '滑坡落石',
    template: '现场发现边坡松动、落石或疑似滑坡迹象，附近人员和车辆存在风险，请尽快核查并设置警戒。'
  },
  {
    key: 'road',
    label: '道路中断',
    template: '现场道路出现塌方、积水、堵塞或桥涵受损，通行受阻，请协调清障和绕行指引。'
  },
  {
    key: 'medical',
    label: '人员受伤',
    template: '现场有人员受伤、身体不适或行动困难，请联系救援人员到场并协助转移就医。'
  },
  {
    key: 'shelter',
    label: '安置需求',
    template: '现场群众或游客需要临时转移安置，请安排避险点、交通接驳和基本生活保障。'
  }
]

const TYPE_KEYWORDS = {
  flood: ['暴雨', '积水', '涨水', '山洪', '内涝', '水位', '淹', '泥石流'],
  landslide: ['滑坡', '塌方', '落石', '崩塌', '边坡', '松动'],
  road: ['道路', '中断', '堵塞', '桥', '交通', '绕行', '塌陷'],
  medical: ['受伤', '昏迷', '急救', '送医', '救护', '摔伤', '不适'],
  shelter: ['安置', '转移', '避险', '疏散', '集合点'],
  sos: ['求助', '救命', '被困', '危险', 'sos', 'SOS']
}

const DISTRICTS = ['永定区', '慈利县', '武陵源区', '桑植县']

const DISTRICT_FALLBACK_COORDS = {
  永定区: { lat: 29.1201, lng: 110.4792 },
  慈利县: { lat: 29.4297, lng: 111.1399 },
  武陵源区: { lat: 29.3502, lng: 110.5446 },
  桑植县: { lat: 29.3992, lng: 110.1640 }
}

const LOCATION_MODES = {
  tourist: ['景区快速选择', '使用当前位置', '手动补充位置'],
  resident: ['村社/道路快速选择', '使用当前位置', '手动补充位置']
}

const LOCATION_MAP = {
  永定区: [
    { name: '天门山索道站', lat: 29.1169, lng: 110.4784 },
    { name: '大庸古城片区', lat: 29.1246, lng: 110.4779 },
    { name: '沙堤街道', lat: 29.1938, lng: 110.4946 },
    { name: '罗水乡大明村', lat: 29.1984, lng: 110.3749 }
  ],
  慈利县: [
    { name: '张家界大峡谷游客中心', lat: 29.3939, lng: 110.6938 },
    { name: '金慈街道长潭河村', lat: 29.4019, lng: 111.1174 },
    { name: '三合镇雷岩村', lat: 29.5486, lng: 111.1258 },
    { name: '金岩土家族乡红联村', lat: 29.4741, lng: 111.0726 }
  ],
  武陵源区: [
    { name: '金鞭溪入口', lat: 29.3472, lng: 110.5587 },
    { name: '黄龙洞出口', lat: 29.3679, lng: 110.6172 },
    { name: '溪布街社区', lat: 29.3526, lng: 110.5447 },
    { name: '标志门广场', lat: 29.3507, lng: 110.5516 }
  ],
  桑植县: [
    { name: '洪家关白族乡', lat: 29.3966, lng: 110.1596 },
    { name: '九天洞景区', lat: 29.6404, lng: 110.1518 },
    { name: '利福塔镇', lat: 29.4567, lng: 110.2169 },
    { name: '官地坪镇', lat: 29.7476, lng: 110.2978 }
  ]
}

const STATUS_FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待处理' },
  { key: 'responding', label: '处理中' },
  { key: 'resolved', label: '已处理' }
]

const STATUS_RANK = {
  pending: 0,
  responding: 1,
  resolved: 2
}

function typeText(type) {
  const item = EVENT_TYPES.find((option) => option.key === type)
  if (item && item.key !== 'other') return item.label
  const map = { other: '其他情况', sos: '紧急求助' }
  return map[type] || type || '现场情况'
}

function statusText(status) {
  const map = { pending: '待处理', responding: '处理中', resolved: '已处理' }
  return map[status] || status || '待处理'
}

function classifyDescription(description) {
  const text = String(description || '')
  for (const type of ['sos', 'flood', 'landslide', 'road', 'medical', 'shelter']) {
    if ((TYPE_KEYWORDS[type] || []).some((keyword) => text.indexOf(keyword) >= 0)) return type
  }
  return 'other'
}

function normalizeIncidents(items) {
  return items.map((item) => ({
    ...item,
    type_text: typeText(item.type),
    status_text: statusText(item.status),
    status_class: item.status || 'pending',
    created_text: String(item.created_at || '').replace('T', ' ')
  })).sort((a, b) => {
    const rankDiff = (STATUS_RANK[a.status] ?? 0) - (STATUS_RANK[b.status] ?? 0)
    if (rankDiff !== 0) return rankDiff
    return String(b.created_at || '').localeCompare(String(a.created_at || ''))
  })
}

function districtIndexOf(district) {
  const index = DISTRICTS.indexOf(district)
  return index >= 0 ? index : 0
}

function locationLabels(district) {
  return (LOCATION_MAP[district] || []).map((item) => item.name)
}

function locationHint(isTourist, modeIndex) {
  if (modeIndex === 0) return isTourist ? '优先选择景区入口、索道站、游客集散点，工作人员能更快定位。' : '优先选择村社、道路、桥涵或屋后边坡等基层可识别点位。'
  if (modeIndex === 1) return '适合不清楚具体地名时使用；现场位置补充可不填，不影响定位和求助。'
  return '不清楚经纬度也可以先提交，建议尽量写清入口、路口、村组、屋后或河沟边。'
}

function formatChosenLocation(location) {
  return [location.name, location.address].filter(Boolean).join('，')
}

function submitConfirmText(payload, isEmergency) {
  return [
    `类型：${typeText(payload.type)}`,
    `区县：${payload.district}`,
    `位置：${payload.scenic_area || '未填写'}`,
    `坐标：${payload.lat}, ${payload.lng}`,
    `描述：${isEmergency ? payload.description.replace(/^SOS：/, '') : payload.description}`
  ].join('\n')
}

function submitErrorMessage(error) {
  const detail = String((error && error.detail) || '')
  if (detail === 'Not authenticated' || !isBackendSession()) {
    return '未登录后端账号，上级端无法看见本次上报。请先退出登录，再用手机号或昵称注册/登录后端账号。'
  }
  if (detail.includes('timeout') || Number((error && error.statusCode) || 0) === 0) {
    return '无法连接后端，请确认服务已启动后重试。'
  }
  return detail || '提交失败，请稍后重试。'
}

Page({
  data: {
    user: null,
    isTourist: false,
    typeIndex: 0,
    typeLabels: EVENT_TYPES.map((item) => item.label),
    autoTypeLabel: '其他情况',
    districtIndex: 0,
    districtLabels: DISTRICTS,
    locationModeIndex: 1,
    locationModeLabels: LOCATION_MODES.resident,
    locationIndex: 0,
    locationLabels: locationLabels(DISTRICTS[0]),
    locationHint: locationHint(false, 1),
    coordinateReady: false,
    statusFilters: STATUS_FILTERS,
    activeStatus: 'all',
    backendReady: false,
    submitting: false,
    reportSubmitting: false,
    sosSubmitting: false,
    notice: '',
    allIncidents: [],
    incidents: [],
    form: {
      description: EVENT_TYPES[0].template,
      district: DISTRICTS[0],
      scenic_area: '',
      lat: '',
      lng: ''
    }
  },

  onLoad() {
    const app = getApp()
    const session = app.loadSession()
    if (!session.token) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }

    const isTourist = session.user.role === 'tourist'
    const districtIndex = districtIndexOf(currentDistrict(session.user.district))
    const district = DISTRICTS[districtIndex]
    const labels = locationLabels(district)

    this.setData({
      user: session.user,
      isTourist,
      districtIndex,
      locationModeLabels: isTourist ? LOCATION_MODES.tourist : LOCATION_MODES.resident,
      locationLabels: labels,
      locationHint: locationHint(isTourist, 1),
      locationModeIndex: 1,
      backendReady: isBackendSession(),
      form: {
        ...this.data.form,
        district,
        scenic_area: '',
        description: isTourist
          ? '我在景区游览时遇到积水、道路受阻或人员滞留，请求现场核实和路线指引。'
          : EVENT_TYPES[0].template
      }
    })
    this.updateAutoType()
  },

  onShow() {
    this.loadIncidents()
  },

  onPullDownRefresh() {
    this.loadIncidents().finally(() => wx.stopPullDownRefresh())
  },

  async loadIncidents() {
    const backendReady = isBackendSession()
    this.setData({ backendReady })
    if (!backendReady) {
      this.setData({
        allIncidents: [],
        notice: '未连接后端账号，请退出后重新登录。'
      })
      this.refreshVisibleIncidents()
      return
    }
    try {
      const result = await api.get('/api/incidents?mine=true')
      const allIncidents = normalizeIncidents(result.items || [])
      this.setData({ allIncidents, notice: '' })
      this.refreshVisibleIncidents()
    } catch (error) {
      this.setData({
        allIncidents: [],
        notice: submitErrorMessage(error)
      })
      this.refreshVisibleIncidents()
    }
  },

  refreshVisibleIncidents() {
    const activeStatus = this.data.activeStatus
    const incidents = this.data.allIncidents
      .filter((item) => activeStatus === 'all' || item.status === activeStatus)
      .slice(0, 20)
    this.setData({ incidents })
  },

  updateForm(key, value) {
    this.setData({ form: { ...this.data.form, [key]: value } })
  },

  clearCoordinate() {
    this.setData({
      coordinateReady: false,
      form: { ...this.data.form, lat: '', lng: '' }
    })
  },

  updateAutoType(description) {
    const type = classifyDescription(description === undefined ? this.data.form.description : description)
    this.setData({ autoTypeLabel: typeText(type) })
  },

  onTypeChange(event) {
    const typeIndex = Number(event.detail.value)
    const selected = EVENT_TYPES[typeIndex] || EVENT_TYPES[0]
    this.setData({
      typeIndex,
      form: { ...this.data.form, description: selected.template }
    })
    this.updateAutoType(selected.template)
  },

  onDescription(event) {
    const description = event.detail.value
    this.updateForm('description', description)
    if (this.data.typeIndex === 0) this.updateAutoType(description)
  },

  onDistrictChange(event) {
    const districtIndex = Number(event.detail.value)
    const district = DISTRICTS[districtIndex]
    const labels = locationLabels(district)
    this.setData({
      districtIndex,
      locationIndex: 0,
      locationLabels: labels,
      form: {
        ...this.data.form,
        district,
        scenic_area: this.data.locationModeIndex === 0 ? (labels[0] || '') : this.data.form.scenic_area
      },
      notice: ''
    })
    this.clearCoordinate()
  },

  onLocationModeChange(event) {
    const locationModeIndex = Number(event.detail.value)
    const labels = locationLabels(this.data.form.district)
    this.setData({
      locationModeIndex,
      locationIndex: 0,
      locationHint: locationHint(this.data.isTourist, locationModeIndex),
      form: {
        ...this.data.form,
        scenic_area: locationModeIndex === 0 ? (labels[0] || '') : ''
      },
      notice: ''
    })
    this.clearCoordinate()
  },

  onLocationChange(event) {
    const locationIndex = Number(event.detail.value)
    const name = this.data.locationLabels[locationIndex] || ''
    this.setData({
      locationIndex,
      form: { ...this.data.form, scenic_area: name },
      notice: ''
    })
    this.clearCoordinate()
  },

  onScenicArea(event) {
    this.updateForm('scenic_area', event.detail.value)
    this.clearCoordinate()
  },

  onLat(event) {
    this.updateForm('lat', Number(event.detail.value))
  },

  onLng(event) {
    this.updateForm('lng', Number(event.detail.value))
  },

  getSelectedLocation() {
    if (this.data.locationModeIndex !== 0) return null
    const locations = LOCATION_MAP[this.data.form.district] || []
    return locations[this.data.locationIndex] || null
  },

  useFallbackCoordinate(reason) {
    if (this.data.locationModeIndex === 1) {
      this.setData({
        notice: `${reason}请授权定位权限，或切换到“手动补充位置”后再提交。模拟器定位不准，请使用真机调试。`
      })
      return
    }
    const fallback = DISTRICT_FALLBACK_COORDS[this.data.form.district] || DISTRICT_FALLBACK_COORDS[DISTRICTS[0]]
    this.setData({
      coordinateReady: true,
      form: {
        ...this.data.form,
        lat: fallback.lat,
        lng: fallback.lng
      },
      notice: `${reason}已使用${this.data.form.district}参考坐标，建议补充现场位置描述。`
    })
  },

  locate() {
    const selected = this.getSelectedLocation()
    if (selected) {
      this.setData({
        coordinateReady: true,
        form: {
          ...this.data.form,
          scenic_area: selected.name,
          lat: selected.lat,
          lng: selected.lng
        },
        notice: ''
      })
      return
    }

    if (wx.chooseLocation) {
      wx.chooseLocation({
        latitude: this.data.form.lat ? Number(this.data.form.lat) : undefined,
        longitude: this.data.form.lng ? Number(this.data.form.lng) : undefined,
        success: (res) => {
          const lat = Number(Number(res.latitude).toFixed(6))
          const lng = Number(Number(res.longitude).toFixed(6))
          const scenicArea = formatChosenLocation(res)
          const district = inferDistrictFromText(scenicArea) || this.data.form.district
          const districtIndex = districtIndexOf(district)
          saveScope({ district, scenic_area: scenicArea, lat, lng })
          this.setData({
            coordinateReady: true,
            districtIndex,
            locationLabels: locationLabels(district),
            form: {
              ...this.data.form,
              district,
              scenic_area: scenicArea || this.data.form.scenic_area,
              lat,
              lng
            },
            notice: '已获取中文位置，请确认后提交。'
          })
        },
        fail: () => {
          this.locateByCoordinate()
        }
      })
      return
    }

    this.locateByCoordinate()
  },

  locateByCoordinate() {
    const isDevtools = getApp().globalData.isDevtools
    wx.getLocation({
      type: 'gcj02',
      isHighAccuracy: true,
      highAccuracyExpireTime: 5000,
      success: (res) => {
        const lat = Number(res.latitude.toFixed(6))
        const lng = Number(res.longitude.toFixed(6))
        const devtoolsHint = isDevtools ? '模拟器定位为调试坐标，真机调试才会显示真实位置。' : ''
        saveScope({ district: this.data.form.district, scenic_area: this.data.form.scenic_area, lat, lng })
        this.setData({
          coordinateReady: true,
          form: {
            ...this.data.form,
            lat,
            lng
          },
          notice: devtoolsHint || '已获取实时坐标，请补充中文现场位置。'
        })
      },
      fail: () => {
        this.useFallbackCoordinate('定位未授权或获取失败，')
      }
    })
  },

  setStatusFilter(event) {
    this.setData({ activeStatus: event.currentTarget.dataset.status })
    this.refreshVisibleIncidents()
  },

  buildSubmitPayload(isEmergency) {
    const description = String(this.data.form.description || '').trim()
    if (!description) {
      this.setData({ notice: '请填写现场描述。' })
      return null
    }
    if (!this.data.form.district) {
      this.setData({ notice: '请选择区县。' })
      return null
    }
    if (!this.data.coordinateReady) {
      this.useFallbackCoordinate('尚未定位，')
      return null
    }

    const selectedType = EVENT_TYPES[this.data.typeIndex] || EVENT_TYPES[0]
    const inferredType = selectedType.key === 'other' ? classifyDescription(description) : selectedType.key
    return {
      ...this.data.form,
      lat: Number(this.data.form.lat),
      lng: Number(this.data.form.lng),
      type: isEmergency ? 'sos' : inferredType,
      description: isEmergency ? `SOS：${description}` : description,
      district: this.data.form.district,
      scenic_area: this.data.form.scenic_area || undefined
    }
  },

  confirmSubmit(payload, isEmergency) {
    return new Promise((resolve) => {
      wx.showModal({
        title: isEmergency ? '确认发送 SOS' : '确认提交上报',
        content: submitConfirmText(payload, isEmergency),
        confirmText: isEmergency ? '发送SOS' : '确认提交',
        cancelText: '返回修改',
        confirmColor: isEmergency ? '#d84a1b' : '#0b7c72',
        success: (res) => resolve(Boolean(res.confirm)),
        fail: () => resolve(false)
      })
    })
  },

  async sendSubmit(payload, isEmergency) {
    if (this.data.submitting) return
    if (!isBackendSession()) {
      this.setData({ notice: submitErrorMessage({ detail: 'Not authenticated' }) })
      return
    }

    const submittingKey = isEmergency ? 'sosSubmitting' : 'reportSubmitting'
    this.setData({
      submitting: true,
      [submittingKey]: true,
      notice: '正在提交...'
    })
    try {
      const created = await api.post('/api/incidents', payload)
      const allIncidents = normalizeIncidents([created, ...this.data.allIncidents])
      this.setData({
        allIncidents,
        notice: isEmergency ? 'SOS 已提交到后端，市级/区县级工作台会优先处置。' : '上报已提交到后端，上级管理端可见，状态为待处理。'
      })
      this.refreshVisibleIncidents()
    } catch (error) {
      this.setData({ notice: submitErrorMessage(error) })
    } finally {
      this.setData({
        submitting: false,
        [submittingKey]: false
      })
    }
  },

  async submit(isEmergency) {
    if (this.data.submitting) return

    const payload = this.buildSubmitPayload(isEmergency)
    if (!payload) return

    const confirmed = await this.confirmSubmit(payload, isEmergency)
    if (!confirmed) {
      this.setData({ notice: '已取消提交，可继续修改内容。' })
      return
    }

    await this.sendSubmit(payload, isEmergency)
  },

  submitReport() {
    this.submit(false)
  },

  submitEmergency() {
    this.submit(true)
  }
})
