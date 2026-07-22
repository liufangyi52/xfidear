const STORAGE_KEY = 'zjj_local_accounts'

function nowText() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function hashText(text) {
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24)
  }
  return String(hash >>> 0)
}

function normalizeUsername(username) {
  return String(username || '').trim()
}

function loadAccounts() {
  return wx.getStorageSync(STORAGE_KEY) || []
}

function saveAccounts(accounts) {
  wx.setStorageSync(STORAGE_KEY, accounts)
}

function clearAccounts() {
  wx.removeStorageSync(STORAGE_KEY)
}

function findAccount(username) {
  const normalized = normalizeUsername(username)
  return loadAccounts().find((account) => account.username === normalized)
}

function publicUser(account) {
  return {
    id: account.id,
    username: account.username,
    role: account.role,
    district: account.district || null,
    community: account.community || null,
    is_local: true
  }
}

function registerAccount(payload) {
  const username = normalizeUsername(payload.username)
  if (findAccount(username)) {
    return {
      ok: false,
      message: '注册失败：该手机号或昵称已在本机注册，请换一个。'
    }
  }

  const accounts = loadAccounts()
  const account = {
    id: Date.now(),
    username,
    role: payload.role,
    salt: String(Date.now()),
    password_hash: '',
    district: null,
    community: null,
    created_at: nowText()
  }
  account.password_hash = hashText(`${account.salt}:${payload.password}`)
  accounts.push(account)
  saveAccounts(accounts)

  return {
    ok: true,
    token: `local-${account.id}-${Date.now()}`,
    user: publicUser(account)
  }
}

function loginAccount(username, password, role) {
  const account = findAccount(username)
  if (!account) {
    return {
      ok: false,
      message: '账号不存在，请先注册；如果这个账号注册在后端，请启动后端后再登录。'
    }
  }
  if (account.role !== role) {
    return {
      ok: false,
      message: '该账号身份不匹配，请返回选择正确身份。'
    }
  }
  if (account.password_hash !== hashText(`${account.salt}:${password}`)) {
    return {
      ok: false,
      message: '登录失败：密码不正确，请重新输入。'
    }
  }
  return {
    ok: true,
    token: `local-${account.id}-${Date.now()}`,
    user: publicUser(account)
  }
}

module.exports = {
  clearAccounts,
  loadAccounts,
  loginAccount,
  registerAccount
}
