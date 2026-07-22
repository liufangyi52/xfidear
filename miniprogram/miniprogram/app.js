const config = require('./utils/config')
const { clearLegacyLocalSession } = require('./utils/session')

function isDevtools() {
  try {
    if (wx.getDeviceInfo) {
      return wx.getDeviceInfo().platform === 'devtools'
    }
    const info = wx.getSystemInfoSync()
    return info.platform === 'devtools'
  } catch (error) {
    return false
  }
}

function resolveServiceUrls() {
  if (isDevtools()) {
    return {
      apiBaseUrl: config.localApiUrl,
      wsBaseUrl: config.localWsUrl
    }
  }
  return {
    apiBaseUrl: config.apiBaseUrl,
    wsBaseUrl: config.wsBaseUrl
  }
}

const serviceUrls = resolveServiceUrls()

App({
  globalData: {
    apiBaseUrl: serviceUrls.apiBaseUrl,
    wsBaseUrl: serviceUrls.wsBaseUrl,
    isDevtools: isDevtools(),
    backendConnected: false,
    token: '',
    user: null,
    socketOpen: false,
    socketTask: null,
    listeners: [],
    reconnectDelay: 3000
  },

  onLaunch() {
    clearLegacyLocalSession()
    this.loadSession()
    if (this.globalData.token) {
      this.connectRealtime()
    }
  },

  loadSession() {
    this.globalData.token = wx.getStorageSync('zjj_token') || ''
    this.globalData.user = wx.getStorageSync('zjj_user') || null
    return {
      token: this.globalData.token,
      user: this.globalData.user
    }
  },

  setSession(token, user) {
    wx.setStorageSync('zjj_token', token)
    wx.setStorageSync('zjj_user', user)
    this.globalData.token = token
    this.globalData.user = user
    this.connectRealtime()
  },

  clearSession() {
    wx.removeStorageSync('zjj_token')
    wx.removeStorageSync('zjj_user')
    this.globalData.token = ''
    this.globalData.user = null
    this.globalData.socketOpen = false
    this.globalData.backendConnected = false
    if (this.globalData.socketTask) {
      this.globalData.socketTask.close()
    }
  },

  onPush(listener) {
    this.globalData.listeners.push(listener)
    return () => {
      this.globalData.listeners = this.globalData.listeners.filter((item) => item !== listener)
    }
  },

  emitPush(payload) {
    this.globalData.listeners.forEach((listener) => listener(payload))
  },

  connectRealtime() {
    const token = this.globalData.token
    if (!token || this.globalData.socketOpen) return
    if (token.indexOf('local-') === 0) return
    if (this.globalData.socketTask) {
      this.globalData.socketTask.close()
    }

    const socketTask = wx.connectSocket({
      url: `${this.globalData.wsBaseUrl}/api/ws/notifications?token=${encodeURIComponent(token)}`
    })
    this.globalData.socketTask = socketTask

    socketTask.onOpen(() => {
      this.globalData.socketOpen = true
      this.globalData.reconnectDelay = 3000
      socketTask.send({ data: 'ping' })
    })
    socketTask.onMessage((event) => {
      let payload = null
      try {
        payload = JSON.parse(event.data)
      } catch (error) {
        return
      }
      if (payload.type === 'message') {
        wx.showToast({ title: '收到上级预警/消息', icon: 'none' })
        this.emitPush(payload)
      }
    })
    socketTask.onClose(() => {
      this.globalData.socketOpen = false
      this.globalData.socketTask = null
      if (this.globalData.token) {
        const delay = this.globalData.reconnectDelay
        this.globalData.reconnectDelay = Math.min(delay * 2, 30000)
        setTimeout(() => this.connectRealtime(), delay)
      }
    })
    socketTask.onError(() => {
      this.globalData.socketOpen = false
    })
  }
})
