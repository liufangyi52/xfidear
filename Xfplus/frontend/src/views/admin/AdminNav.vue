<script setup lang="ts">
import { loadSession } from '../../auth'
import { workbenchPathForRole } from '../../workflows'

const user = loadSession()
const workbenchPath = workbenchPathForRole(user?.role)
</script>

<template>
  <nav class="admin-nav">
    <RouterLink :to="workbenchPath">工作台</RouterLink>
  </nav>
</template>
