let lastOfflineToastAt = 0

function showOfflineToast(title, intervalMs = 8000) {
  const now = Date.now()
  if (now - lastOfflineToastAt < intervalMs) return
  lastOfflineToastAt = now
  wx.showToast({ title, icon: 'none' })
}

module.exports = {
  showOfflineToast
}
