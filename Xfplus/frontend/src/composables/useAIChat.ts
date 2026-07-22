import { ref } from 'vue'
import { api } from '../api'

export function useAIChat() {
  const fallbackNotice = ref('')
  const loading = ref(false)

  async function ask(question: string) {
    loading.value = true
    try {
      const { data } = await api.post('/api/ask', { question })
      fallbackNotice.value = data.fallback_used ? '当前 AI 使用备用模式，回答质量可能有波动' : ''
      return data
    } finally {
      loading.value = false
    }
  }

  return { ask, fallbackNotice, loading }
}
