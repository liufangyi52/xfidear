const config = require('./config')

const BAIDU_GEOCODER_URL = 'https://api.map.baidu.com/reverse_geocoding/v3/'

function requestMap(data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BAIDU_GEOCODER_URL,
      method: 'GET',
      data: {
        ak: config.baiduMapAk,
        output: 'json',
        coordtype: 'gcj02ll',
        extensions_poi: 1,
        ...data
      },
      timeout: 10000,
      success(res) {
        const body = res.data || {}
        if (res.statusCode >= 200 && res.statusCode < 300 && body.status === 0) {
          resolve(body.result || {})
          return
        }
        reject({
          detail: body.message || body.msg || `百度地图服务请求失败：${body.status}`,
          statusCode: res.statusCode
        })
      },
      fail(error) {
        reject({
          detail: error.errMsg || '百度地图服务请求失败',
          errMsg: error.errMsg || '',
          statusCode: 0
        })
      }
    })
  })
}

async function reverseGeocoder(lat, lng) {
  const result = await requestMap({
    location: `${lat},${lng}`
  })
  const address = result.formatted_address || ''
  const semantic = result.sematic_description || ''
  const poi = result.pois && result.pois[0] && result.pois[0].name
  return {
    address,
    title: semantic || poi || address,
    raw: result
  }
}

module.exports = {
  reverseGeocoder
}
