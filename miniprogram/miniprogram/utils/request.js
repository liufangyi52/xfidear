const config = require('./config')

const DEV_API_URL = config.localApiUrl

function buildUrl(baseUrl, path) {
  return `${baseUrl}${path}`
}

function normalizeError(error, statusCode = 0) {
  const errMsg = String((error && error.errMsg) || '')
  let detail = error && (error.detail || error.errMsg) ? (error.detail || error.errMsg) : '网络请求失败'

  if (errMsg.includes('url not in domain list')) {
    detail = '请求被微信域名校验拦截，请确认 project.private.config.json 中 urlCheck 为 false 后重新编译。'
  } else if (errMsg.includes('request:fail')) {
    detail = '无法连接后端，请确认已执行 start-foreground.ps1，后端监听 0.0.0.0:8000，且小程序 LAN IP 配置为当前电脑地址。'
  }

  return {
    detail,
    errMsg,
    statusCode
  }
}

function doRequest(baseUrl, options, header) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: buildUrl(baseUrl, options.url),
      method: options.method || 'GET',
      data: options.data || {},
      header,
      timeout: 15000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
          return
        }
        reject(Object.assign({ statusCode: res.statusCode }, res.data || res))
      },
      fail(error) {
        reject(normalizeError(error, 0))
      }
    })
  })
}

function candidateBaseUrls(primaryUrl) {
  const urls = [primaryUrl]
  if (primaryUrl !== DEV_API_URL) urls.push(DEV_API_URL)
  return urls.filter((url, index) => url && urls.indexOf(url) === index)
}

async function request(options) {
  const app = getApp()
  const token = app.globalData.token || wx.getStorageSync('zjj_token') || ''
  const header = Object.assign({}, options.header || {})
  if (token) {
    header.Authorization = `Bearer ${token}`
  }

  const baseUrls = candidateBaseUrls(app.globalData.apiBaseUrl)
  let lastError = null

  for (let index = 0; index < baseUrls.length; index += 1) {
    const baseUrl = baseUrls[index]
    try {
      const result = await doRequest(baseUrl, options, header)
      if (app.globalData.apiBaseUrl !== baseUrl) {
        app.globalData.apiBaseUrl = baseUrl
        app.globalData.wsBaseUrl = baseUrl.replace('http://', 'ws://').replace('https://', 'wss://')
      }
      app.globalData.backendConnected = true
      return result
    } catch (error) {
      lastError = error
      if (error.statusCode === 401) {
        if (options.url.indexOf('/api/auth/') === 0) {
          throw error
        }
        app.clearSession()
        wx.reLaunch({ url: '/pages/login/login' })
        throw error
      }
      if (error.statusCode !== 0) {
        throw error
      }
    }
  }

  app.globalData.backendConnected = false
  throw normalizeError(lastError, lastError && lastError.statusCode ? lastError.statusCode : 0)
}

module.exports = {
  get(url) {
    return request({ url })
  },
  post(url, data) {
    return request({ url, method: 'POST', data })
  },
  put(url, data) {
    return request({ url, method: 'PUT', data })
  }
}
