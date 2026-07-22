const api = require('../../utils/request')
const { filterCorruptedMessages, isCorruptedMessage } = require('../../utils/text')
const { currentDistrict } = require('../../utils/location_scope')

const UPPER_SENDER_ROLES = ['city_admin', 'county_admin', 'community_admin']
const WARNING_SOURCE_TYPES = ['alert_push', 'alert_forward', 'assistant_alert_push']

function normalizeMessage(payload) {
  if (!payload) return null
  const message = payload.message || payload.data || payload
  return isCorruptedMessage(message) ? null : message
}

function isUpperMessage(message) {
  return UPPER_SENDER_ROLES.indexOf(message && message.sender_role) >= 0
}

function isWarningMessage(message) {
  return isUpperMessage(message) && WARNING_SOURCE_TYPES.indexOf(message.source_type) >= 0
}

function levelText(level) {
  const map = {
    orange: '橙色',
    red: '红色',
    yellow: '黄色',
    blue: '蓝色',
    high: '高风险',
    critical: '极高风险',
    medium: '中风险',
    low: '低风险'
  }
  return map[level] || level || '预警'
}

Page({
  data: {
    user: null,
    isTourist: false,
    weather: {},
    latestAlert: null,
    latestAlertLevelText: '',
    latestAlertText: '',
    realtimeMessage: null,
    riskPoints: [],
    loadError: ''
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
      isTourist: session.user && session.user.role === 'tourist'
    })
    this.offPush = app.onPush((payload) => this.handlePush(payload))
  },

  onShow() {
    this.load()
  },

  onUnload() {
    if (this.offPush) this.offPush()
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh())
  },

  handlePush(payload) {
    const message = normalizeMessage(payload)
    if (message && isWarningMessage(message)) {
      this.setData({ realtimeMessage: message, loadError: '' })
    }
  },

  async load() {
    try {
      const district = currentDistrict(this.data.user && this.data.user.district)
      const inboxUrl = district ? `/api/messages/inbox?district=${encodeURIComponent(district)}` : '/api/messages/inbox'
      const [risk, inboxResult] = await Promise.all([
        api.get('/api/risk/current'),
        api.get(inboxUrl).catch(() => [])
      ])
      let warningMessages = filterCorruptedMessages(inboxResult).filter(isWarningMessage)
      if (!warningMessages.length && district) {
        const fallbackInbox = await api.get('/api/messages/inbox').catch(() => [])
        warningMessages = filterCorruptedMessages(fallbackInbox).filter(isWarningMessage)
      }
      const latestAlert = warningMessages[0] || null
      this.setData({
        latestAlert,
        latestAlertLevelText: latestAlert ? levelText('上级预警') : '',
        latestAlertText: latestAlert ? latestAlert.content : '',
        weather: risk.weather || {},
        riskPoints: (risk.points || []).slice(0, this.data.isTourist ? 3 : 2),
        realtimeMessage: latestAlert,
        loadError: ''
      })
    } catch (error) {
      this.setData({
        latestAlert: null,
        latestAlertLevelText: '',
        latestAlertText: '',
        weather: {},
        riskPoints: [],
        realtimeMessage: null,
        loadError: (error && error.detail) || '无法连接后端，请确认服务已启动后点击刷新'
      })
    }
  },

  goMessages() {
    wx.switchTab({ url: '/pages/messages/messages' })
  },

  goRisk() {
    wx.switchTab({ url: '/pages/risk/risk' })
  },

  openAlert() {
    if (!this.data.latestAlert) return
    wx.showModal({
      title: this.data.latestAlert.title,
      content: this.data.latestAlertText,
      showCancel: false
    })
  }
})
