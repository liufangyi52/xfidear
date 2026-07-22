import { ref } from 'vue'

export type SpeechStatus = 'idle' | 'speaking' | 'needs_user_activation' | 'unsupported_or_blocked'

const voicePermissionGranted = ref(localStorage.getItem('zjj_voice_permission') === 'granted')
const failureCount = ref(0)

export function useSpeech() {
  const status = ref<SpeechStatus>('idle')
  const message = ref('')
  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window

  function setBlocked() {
    status.value = 'unsupported_or_blocked'
    message.value = '您的浏览器不支持语音播报，可尝试下载文案'
  }

  function activate() {
    if (!isSupported) {
      setBlocked()
      return
    }
    try {
      const utterance = new SpeechSynthesisUtterance('')
      utterance.lang = 'zh-CN'
      window.speechSynthesis.speak(utterance)
      voicePermissionGranted.value = true
      localStorage.setItem('zjj_voice_permission', 'granted')
      status.value = 'idle'
      message.value = '语音已激活，请点击播放按钮收听'
    } catch {
      status.value = 'needs_user_activation'
      message.value = '请先点击页面任意位置，再使用语音播报'
    }
  }

  function speak(text: string, lang = 'zh-CN') {
    if (!isSupported) {
      setBlocked()
      return status.value
    }
    if (!voicePermissionGranted.value) {
      status.value = 'needs_user_activation'
      message.value = '请先点击页面任意位置，再使用语音播报'
    }

    try {
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = lang
      utterance.rate = 0.95
      utterance.onstart = () => {
        status.value = 'speaking'
        message.value = ''
        voicePermissionGranted.value = true
        localStorage.setItem('zjj_voice_permission', 'granted')
      }
      utterance.onend = () => {
        status.value = 'idle'
      }
      utterance.onerror = () => {
        failureCount.value += 1
        status.value = failureCount.value <= 1 ? 'needs_user_activation' : 'unsupported_or_blocked'
        message.value =
          status.value === 'needs_user_activation'
            ? '请再点一次播放按钮以激活语音'
            : '您的浏览器不支持语音播报，可尝试下载文案'
      }
      window.speechSynthesis.speak(utterance)
      window.setTimeout(() => {
        if (!window.speechSynthesis.speaking && !window.speechSynthesis.pending && status.value !== 'idle') {
          status.value = 'needs_user_activation'
          message.value = '请再点一次播放按钮以激活语音'
        }
      }, 350)
    } catch {
      failureCount.value += 1
      status.value = failureCount.value <= 1 ? 'needs_user_activation' : 'unsupported_or_blocked'
      message.value =
        status.value === 'needs_user_activation'
          ? '请再点一次播放按钮以激活语音'
          : '您的浏览器不支持语音播报，可尝试下载文案'
    }
    return status.value
  }

  function stop() {
    if (isSupported) window.speechSynthesis.cancel()
    status.value = 'idle'
  }

  return { status, message, isSupported, voicePermissionGranted, speak, stop, activate }
}
