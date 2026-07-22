// 真机调试：改成你电脑的局域网 IP（手机和电脑需同一 Wi-Fi）
const LAN_API_HOST = '172.23.226.63'
const API_PORT = 8000

module.exports = {
  // 开发者工具模拟器优先使用本机地址
  localApiUrl: `http://127.0.0.1:${API_PORT}`,
  // 真机调试使用局域网 IP
  apiBaseUrl: `http://${LAN_API_HOST}:${API_PORT}`,
  wsBaseUrl: `ws://${LAN_API_HOST}:${API_PORT}`,
  localWsUrl: `ws://127.0.0.1:${API_PORT}`,
  // 百度地图 AK：需在百度地图开放平台申请并绑定小程序 AppID
  baiduMapAk: 'pkVEfFZHHnTcXX3O2Hye6HLG2lkteyBa'
}
