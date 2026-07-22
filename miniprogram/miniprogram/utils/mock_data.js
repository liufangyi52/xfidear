function formatNow() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const alerts = [
  {
    id: 'mock-alert-wly-rain',
    title: '武陵源区暴雨诱发山洪滑坡风险橙色预警',
    level: 'orange',
    advice: '未来 6 小时暂停涉水游览，远离溪谷、陡坡和临崖路段，服从景区广播与工作人员引导。',
    audience_messages: {
      resident: '请武陵源低洼地带居民关注雨情，提前检查排水沟渠，老人儿童优先转移至安全区域。',
      tourist: '金鞭溪、老磨湾周边游客请停止涉水游览，跟随工作人员前往最近游客中心或标志门广场。'
    },
    created_at: formatNow(),
    pushed_at: formatNow()
  }
]

const risk = {
  weather: {
    summary: '武陵源、天门山一带有中到大雨，局地短时强降雨',
    rainfall_24h: 42,
    source: '本地演示数据'
  },
  points: [
    {
      id: 'mock-risk-wly-rain',
      name: '武陵源金鞭溪沿线崩塌隐患点',
      risk_level: 'high',
      risk_score: 86,
      district: '武陵源区',
      scenic_area: '金鞭溪',
      lat: 29.3472,
      lng: 110.5587,
      action: '立即加强巡查，暂停高风险游线，组织临坡住户和滞留游客转移。',
      nearby_shelter: {
        name: '武陵源区暴雨预警临时避雨安全点',
        distance_km: 0.97
      }
    },
    {
      id: 'mock-risk-yd-road',
      name: '天门山索道站周边积水风险点',
      risk_level: 'medium',
      risk_score: 72,
      district: '永定区',
      scenic_area: '天门山索道站',
      lat: 29.1169,
      lng: 110.4784,
      action: '提醒游客避开临水临坡路段，必要时启用游客中心临时避雨区。',
      nearby_shelter: {
        name: '天门山景区游客应急服务点',
        distance_km: 0.42
      }
    }
  ]
}

const incidents = [
  {
    id: 'mock-incident-road',
    type: 'road',
    description: '天门山索道站外侧道路出现短时积水，现场已提醒游客绕行并等待进一步排查。',
    district: '永定区',
    scenic_area: '天门山索道站',
    lat: 29.1169,
    lng: 110.4784,
    status: 'responding',
    created_at: formatNow()
  }
]

const messages = [
  {
    id: 'mock-message-transfer',
    title: '转移避险提醒',
    content: '遇山洪、滑坡、泥石流风险时，请按现场干部指引前往村部、游客中心等安全地点。',
    status: '模拟预警',
    created_at: formatNow()
  }
]

module.exports = {
  alerts,
  incidents,
  messages,
  risk
}
