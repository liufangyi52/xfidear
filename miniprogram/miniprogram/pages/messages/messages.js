const api = require('../../utils/request')
const { filterCorruptedMessages } = require('../../utils/text')
const { currentDistrict } = require('../../utils/location_scope')

const DISTRICTS = ['永定区', '武陵源区', '桑植县', '慈利县']

function statusText(status) {
  const map = {
    sent: '已发送',
    pending: '待处理',
    pending_review: '待审核',
    replied: '已回复',
    reviewed: '已处理',
    forwarded: '已转派',
    closed: '已关闭',
    cancelled: '已撤销',
    '模拟预警': '模拟预警'
  }
  return map[status] || status || '消息'
}

function withStatusText(messages) {
  return messages.map((item, index) => ({
    ...item,
    speech_id: String(item.id || `message-${index}`),
    status_text: statusText(item.status),
    can_cancel: item.source_type === 'public_suggestion' && ['pending_review', 'pending'].includes(item.status)
  }))
}

function speechText(message) {
  return message.content || ''
}

Page({
  data: {
    user: null,
    isTourist: false,
    districtLabels: DISTRICTS,
    districtIndex: 0,
    messages: [],
    sending: false,
    notice: '',
    lastSubmittedId: '',
    detailOpen: false,
    detailRows: [],
    speakingMessageId: '',
    speechStatus: 'idle',
    suggestion: {
      title: '现场信息建议',
      content: '',
      district: '',
      community: ''
    }
  },

  onLoad() {
    const app = getApp()
    const session = app.loadSession()
    if (!session.token) {
      wx.reLaunch({ url: '/pages/login/login' })
      return
    }
    const districtIndex = Math.max(DISTRICTS.indexOf(currentDistrict(session.user.district)), 0)
    const district = DISTRICTS[districtIndex]
    this.setData({
      user: session.user,
      isTourist: session.user.role === 'tourist',
      districtIndex,
      suggestion: {
        ...this.data.suggestion,
        district,
        community: session.user.community || ''
      }
    })
    this.offPush = app.onPush(() => this.load())
  },

  onShow() {
    this.load()
  },

  onUnload() {
    if (this.offPush) this.offPush()
    this.destroySpeech()
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh())
  },

  setupSpeechAudio() {
    if (this.speechAudio) return this.speechAudio
    const audio = wx.createInnerAudioContext()
    audio.obeyMuteSwitch = false
    audio.onEnded(() => this.resetSpeech())
    audio.onError(() => {
      wx.showToast({ title: '语音播放失败', icon: 'none' })
      this.resetSpeech()
    })
    this.speechAudio = audio
    return audio
  },

  resetSpeech() {
    this.setData({
      speakingMessageId: '',
      speechStatus: 'idle'
    })
  },

  destroySpeech() {
    if (this.speechAudio) {
      this.speechAudio.destroy()
      this.speechAudio = null
    }
    this.resetSpeech()
  },

  playSpeech(src, messageId) {
    const audio = this.setupSpeechAudio()
    audio.stop()
    audio.src = src
    audio.play()
    this.setData({
      speakingMessageId: messageId,
      speechStatus: 'playing'
    })
  },

  pauseSpeech() {
    if (this.speechAudio) {
      this.speechAudio.pause()
      this.setData({ speechStatus: 'paused' })
    }
  },

  resumeSpeech() {
    if (this.speechAudio) {
      this.speechAudio.play()
      this.setData({ speechStatus: 'playing' })
    }
  },

  toggleSpeech(event) {
    const index = Number(event.currentTarget.dataset.index)
    const message = this.data.messages[index]
    if (!message) return

    const messageId = message.speech_id
    if (this.data.speakingMessageId === messageId && this.data.speechStatus === 'playing') {
      this.pauseSpeech()
      return
    }
    if (this.data.speakingMessageId === messageId && this.data.speechStatus === 'paused') {
      this.resumeSpeech()
      return
    }
    if (this.data.speakingMessageId === messageId && this.data.speechStatus === 'loading') return

    this.setData({
      speakingMessageId: messageId,
      speechStatus: 'loading'
    })
    this.playBaiduSpeech(message, messageId)
  },

  async playBaiduSpeech(message, messageId) {
    try {
      const result = await api.post('/api/tts/baidu', { text: speechText(message).slice(0, 500) })
      const audioPath = `${wx.env.USER_DATA_PATH}/zjj-tts-${messageId}-${Date.now()}.mp3`
      wx.getFileSystemManager().writeFile({
        filePath: audioPath,
        data: result.audio_base64,
        encoding: 'base64',
        success: () => this.playSpeech(audioPath, messageId),
        fail: () => {
          wx.showToast({ title: '语音文件保存失败', icon: 'none' })
          this.resetSpeech()
        }
      })
    } catch (error) {
      wx.showToast({ title: (error && error.detail) || '语音生成失败', icon: 'none' })
      this.resetSpeech()
    }
  },

  async load() {
    try {
      const district = currentDistrict(this.data.suggestion.district)
      const url = district ? `/api/messages/inbox?district=${encodeURIComponent(district)}` : '/api/messages/inbox'
      const messages = await api.get(url)
      this.setData({
        messages: withStatusText(filterCorruptedMessages(messages)),
        notice: ''
      })
    } catch (error) {
      this.setData({
        messages: [],
        notice: (error && error.detail) || '无法连接后端，请确认服务已启动后刷新'
      })
    }
  },

  setSuggestion(key, value) {
    this.setData({ suggestion: { ...this.data.suggestion, [key]: value } })
  },

  onSuggestionTitle(event) {
    this.setSuggestion('title', event.detail.value)
  },

  onSuggestionDistrictChange(event) {
    const districtIndex = Number(event.detail.value)
    const district = DISTRICTS[districtIndex] || DISTRICTS[0]
    this.setData({
      districtIndex,
      suggestion: {
        ...this.data.suggestion,
        district
      }
    })
  },

  onSuggestionCommunity(event) {
    this.setSuggestion('community', event.detail.value)
  },

  onSuggestionContent(event) {
    this.setSuggestion('content', event.detail.value)
  },

  async submitSuggestion() {
    const form = this.data.suggestion
    if (!form.title.trim() || !form.content.trim()) {
      this.setData({ notice: '请填写标题和内容。' })
      return
    }
    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: '确认提交建议',
        content: `标题：${form.title.trim()}\n区县：${form.district || '未填写'}\n位置：${form.community || '未填写'}\n\n提交后上级管理端可见，待审核前可撤销。`,
        confirmText: '确认提交',
        cancelText: '返回修改',
        success: (res) => resolve(Boolean(res.confirm)),
        fail: () => resolve(false)
      })
    })
    if (!confirmed) {
      this.setData({ notice: '已取消提交，可继续修改。' })
      return
    }
    this.setData({ sending: true, notice: '正在提交...' })
    try {
      const created = await api.post('/api/messages/suggestions', {
        title: form.title.trim(),
        content: form.content.trim(),
        district: form.district || this.data.user.district || '',
        community: form.community || this.data.user.community || ''
      })
      this.setData({
        notice: '建议已提交。如需修改，可在审核前点击消息列表中的“撤销”。',
        lastSubmittedId: created.id,
        suggestion: { ...form, content: '' }
      })
      await this.load()
    } catch (error) {
      this.setData({ notice: error.detail || '提交失败，请稍后再试。' })
    } finally {
      this.setData({ sending: false })
    }
  },

  async cancelSuggestion(event) {
    const id = Number(event.currentTarget.dataset.id)
    if (!id) return
    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: '撤销建议',
        content: '撤销后上级管理端将不再按待审核建议处理，确认撤销吗？',
        confirmText: '确认撤销',
        cancelText: '暂不撤销',
        confirmColor: '#d84a1b',
        success: (res) => resolve(Boolean(res.confirm)),
        fail: () => resolve(false)
      })
    })
    if (!confirmed) return
    try {
      await api.post(`/api/messages/${id}/cancel`, {})
      this.setData({ notice: '建议已撤销。', lastSubmittedId: '' })
      await this.load()
    } catch (error) {
      this.setData({ notice: error.detail || '撤销失败，该建议可能已被处理。' })
    }
  },

  showMessageDetail(event) {
    const index = Number(event.currentTarget.dataset.index)
    const message = this.data.messages[index]
    if (!message) return
    this.setData({
      detailOpen: true,
      detailRows: [
        { label: '标题', value: message.title || '无标题' },
        { label: '状态', value: message.status_text || '消息' },
        { label: '区县', value: message.target_district || '未填写' },
        { label: '位置', value: message.target_community || '未填写' },
        { label: '时间', value: message.created_at || '--' },
        { label: '内容', value: message.content || '无内容' },
        ...(message.reply_content ? [{ label: '回复', value: message.reply_content }] : [])
      ]
    })
  },

  closeMessageDetail() {
    this.setData({ detailOpen: false, detailRows: [] })
  },

  noop() {
  }
})
