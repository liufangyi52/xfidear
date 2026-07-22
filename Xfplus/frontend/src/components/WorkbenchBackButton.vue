<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import { loadSession } from '../auth'
import { workbenchPathForRole } from '../workflows'

const route = useRoute()
const router = useRouter()
const user = loadSession()
const target = workbenchPathForRole(user?.role)
const isEmbedded = computed(() => route.query.embedded === '1' && window.parent !== window)

function returnToWorkbench() {
  if (isEmbedded.value && window.parent !== window) {
    window.parent.postMessage({ type: 'xfplus:close-bigscreen-workspace' }, window.location.origin)
    return
  }

  router.push(target)
}
</script>

<template>
  <button type="button" class="ghost-button back-workbench" :class="{ 'is-embedded': isEmbedded }" @click="returnToWorkbench">
    <ArrowLeft :size="16" />
    {{ isEmbedded ? '返回指挥平台' : '返回工作台' }}
  </button>
</template>
