const { currentDistrict, inferDistrictFromText, readScope, saveScope } = require('../../utils/location_scope')

function roleText(role) {
  return role === 'tourist' ? '游客' : '居民'
}

function formatChosenLocation(location) {
  return [location.name, location.address].filter(Boolean).join('，')
}

Page({
  data: {
    user: {},
    roleLabel: '',
    locationScope: {}
  },

  onShow() {
    this.refreshLocationScope()
    const app = getApp()
    const session = app.loadSession()
    if (!session.token) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.setData({
      user: session.user,
      roleLabel: roleText(session.user.role),
      locationScope: readScope()
    })
  },

  refreshLocationScope() {
    this.setData({ locationScope: readScope() })
  },

  updateLocation() {
    if (!wx.chooseLocation) return
    wx.chooseLocation({
      success: (res) => {
        const lat = Number(Number(res.latitude).toFixed(6))
        const lng = Number(Number(res.longitude).toFixed(6))
        const scenicArea = formatChosenLocation(res)
        const district = inferDistrictFromText(scenicArea) || currentDistrict(this.data.user.district)
        saveScope({ district, scenic_area: scenicArea, lat, lng })
        this.refreshLocationScope()
        wx.showToast({ title: '位置已更新', icon: 'none' })
      }
    })
  },

  logout() {
    getApp().clearSession()
    wx.reLaunch({ url: '/pages/login/login' })
  }
})
