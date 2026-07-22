const DISTRICTS = ['永定区', '武陵源区', '桑植县', '慈利县']
const STORAGE_KEY = 'zjj_current_location_scope'

const DISTRICT_KEYWORDS = {
  永定区: ['永定区', '张家界学院', '温泉路', '天门山', '大庸桥', '官黎坪', '崇文', '沙堤'],
  武陵源区: ['武陵源区', '武陵源', '黄龙洞', '宝峰湖', '金鞭溪', '标志门', '溪布街'],
  桑植县: ['桑植县', '桑植', '洪家关', '九天洞', '利福塔'],
  慈利县: ['慈利县', '慈利', '大峡谷', '江垭', '金慈']
}

function inferDistrictFromText(text) {
  const source = String(text || '')
  return DISTRICTS.find((district) => (
    DISTRICT_KEYWORDS[district] || [district]
  ).some((keyword) => source.indexOf(keyword) >= 0)) || ''
}

function readScope() {
  return wx.getStorageSync(STORAGE_KEY) || {}
}

function saveScope(scope) {
  const current = readScope()
  const next = {
    ...current,
    ...scope,
    updated_at: new Date().toISOString()
  }
  wx.setStorageSync(STORAGE_KEY, next)
  return next
}

function currentDistrict(fallback = '') {
  return readScope().district || fallback || ''
}

module.exports = {
  DISTRICTS,
  currentDistrict,
  inferDistrictFromText,
  readScope,
  saveScope
}
