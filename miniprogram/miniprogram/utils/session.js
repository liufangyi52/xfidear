function getToken() {
  return getApp().globalData.token || wx.getStorageSync('zjj_token') || ''
}

function isBackendSession() {
  const token = getToken()
  return Boolean(token) && token.indexOf('local-') !== 0
}

function isLocalSession() {
  const token = getToken()
  return Boolean(token) && token.indexOf('local-') === 0
}

function clearLegacyLocalSession() {
  if (!isLocalSession()) return false
  getApp().clearSession()
  wx.removeStorageSync('zjj_local_accounts')
  return true
}

module.exports = {
  clearLegacyLocalSession,
  getToken,
  isBackendSession,
  isLocalSession
}
