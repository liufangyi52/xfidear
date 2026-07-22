const api = require('../../utils/request')
const { clearLegacyLocalSession } = require('../../utils/session')

const PHONE_PATTERN = /^1[3-9]\d{9}$/
const NICKNAME_PATTERN = /^[A-Za-z0-9_\u4e00-\u9fa5]{2,20}$/
const REGISTER_PASSWORD_PATTERN = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,16}$/
const DEMO_USERS = ['resident_demo', 'tourist_demo']
const ROLE_LABELS = {
  resident: '居民',
  tourist: '游客'
}
const DEMO_ACCOUNT = {
  resident: { username: 'resident_demo', password: '123456' },
  tourist: { username: 'tourist_demo', password: '123456' }
}

function isValidAccount(value) {
  return PHONE_PATTERN.test(value) || NICKNAME_PATTERN.test(value) || DEMO_USERS.includes(value)
}

function isNetworkError(error) {
  return Number((error && error.statusCode) || 0) === 0
}

function friendlyError(error, fallback) {
  const detail = error && error.detail
  const detailText = Array.isArray(detail) ? '' : String(detail || '')
  const errMsg = String((error && error.errMsg) || '')
  const statusCode = Number((error && error.statusCode) || 0)
  const map = {
    'Username already exists': '注册失败：该手机号或昵称已被使用，请换一个。',
    'Invalid username or password': '登录失败：账号不存在或密码不正确。',
    'Not authenticated': '登录已失效，请重新登录。'
  }

  if (map[detailText]) return map[detailText]
  if (Array.isArray(detail)) return '提交信息格式不正确，请检查手机号或昵称、密码。'
  if (errMsg.includes('timeout')) return '请求超时，请确认后端服务已启动。'
  if (errMsg.includes('url not in domain list')) return '请求地址未加入合法域名，请在开发工具中关闭域名校验。'
  if (errMsg.includes('request:fail') || statusCode === 0) {
    return '无法连接后端，请先启动后端服务。居民/游客端必须与上级管理端共用同一后端。'
  }
  if (statusCode >= 500) return '后端服务异常，请查看后端控制台报错。'
  return detailText || fallback
}

Page({
  data: {
    step: 'choose',
    mode: 'login',
    role: '',
    roleLabel: '',
    username: '',
    password: '',
    loading: false,
    notice: '',
    noticeType: 'error'
  },

  onLoad() {
    if (clearLegacyLocalSession()) {
      this.setNotice('已清除旧的本机临时登录。请使用后端账号登录，上级管理端才能看见上报数据。', 'error')
      return
    }
    const app = getApp()
    const session = app.loadSession()
    if (session.token) {
      wx.switchTab({ url: '/pages/home/home' })
    }
  },

  setNotice(notice, noticeType = 'error') {
    this.setData({ notice, noticeType })
  },

  chooseResident() {
    this.enterRole('resident')
  },

  chooseTourist() {
    this.enterRole('tourist')
  },

  enterRole(role) {
    this.setData({
      step: 'form',
      mode: 'login',
      role,
      roleLabel: ROLE_LABELS[role],
      username: '',
      password: '',
      notice: '',
      noticeType: 'error'
    })
  },

  backChoose() {
    this.setData({
      step: 'choose',
      mode: 'login',
      role: '',
      roleLabel: '',
      username: '',
      password: '',
      notice: '',
      noticeType: 'error'
    })
  },

  showLogin() {
    this.setData({
      mode: 'login',
      username: '',
      password: '',
      notice: '',
      noticeType: 'error'
    })
  },

  showRegister() {
    this.setData({
      mode: 'register',
      username: '',
      password: '',
      notice: '',
      noticeType: 'error'
    })
  },

  useDemoAccount() {
    const demo = DEMO_ACCOUNT[this.data.role]
    if (!demo) return
    this.setData({
      username: demo.username,
      password: demo.password,
      notice: '已填入演示账号，点击登录即可连接后端。',
      noticeType: 'success'
    })
  },

  onUsername(event) {
    this.setData({ username: event.detail.value })
  },

  onPassword(event) {
    this.setData({ password: event.detail.value })
  },

  validateBase() {
    const username = this.data.username.trim()
    const password = this.data.password

    if (!this.data.role) {
      this.setNotice('请先选择身份。')
      return false
    }
    if (!username || !password.trim()) {
      this.setNotice('请填写手机号或昵称、密码。')
      return false
    }
    if (this.data.mode === 'register' && DEMO_USERS.includes(username)) {
      this.setNotice('这是系统演示账号，不能重复注册；请返回登录直接使用。')
      return false
    }
    if (!isValidAccount(username)) {
      this.setNotice('手机号需为11位大陆手机号；昵称支持中文、英文、数字或下划线，长度2至20位。')
      return false
    }
    if (this.data.mode === 'register' && !REGISTER_PASSWORD_PATTERN.test(password)) {
      this.setNotice('注册失败：密码需为8至16位，并同时包含字母和数字。')
      return false
    }
    return true
  },

  enterApp(result, toastTitle) {
    getApp().setSession(result.token, result.user)
    if (toastTitle) {
      wx.showToast({ title: toastTitle, icon: 'none' })
    }
    wx.switchTab({ url: '/pages/home/home' })
  },

  afterRegisterSuccess(username) {
    this.setData({
      mode: 'login',
      username,
      password: '',
      loading: false,
      notice: '注册成功，账号已写入后端。请输入密码登录，上级管理端即可看见后续上报。',
      noticeType: 'success'
    })
  },

  async login() {
    if (!this.validateBase()) return
    const username = this.data.username.trim()
    const password = this.data.password
    this.setData({ loading: true, notice: '', noticeType: 'error' })
    try {
      const result = await api.post('/api/auth/login', { username, password })
      if (result.user.role !== this.data.role) {
        this.setNotice(`该账号不是${this.data.roleLabel}身份，请返回选择正确身份。`)
        return
      }
      this.enterApp(result, '已连接后端')
    } catch (error) {
      this.setNotice(friendlyError(error, '登录失败：请确认账号已注册，并检查密码。'))
    } finally {
      this.setData({ loading: false })
    }
  },

  async register() {
    if (!this.validateBase()) return
    const username = this.data.username.trim()
    const password = this.data.password
    const role = this.data.role
    this.setData({ loading: true, notice: '', noticeType: 'error' })
    try {
      await api.post('/api/auth/register', { username, password, role })
      this.afterRegisterSuccess(username)
    } catch (error) {
      this.setNotice(friendlyError(error, '注册失败：请检查手机号或昵称是否已存在。'))
    } finally {
      this.setData({ loading: false })
    }
  },

  submit() {
    if (this.data.mode === 'register') {
      this.register()
      return
    }
    this.login()
  }
})
