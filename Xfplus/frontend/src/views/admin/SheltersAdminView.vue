<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AdminNav from './AdminNav.vue'
import { api } from '../../api'
import type { Shelter } from '../../types'

const shelters = ref<Shelter[]>([])

onMounted(async () => {
  shelters.value = (await api.get('/api/shelters')).data
})
</script>

<template>
  <section class="admin-page">
    <AdminNav />
    <div class="admin-content">
      <div class="page-head">
        <p class="eyebrow">Shelters</p>
        <h1>安置点查看</h1>
      </div>
      <div class="panel">
        <div v-for="shelter in shelters" :key="shelter.id" class="admin-row">
          <div>
            <strong>{{ shelter.name }}</strong>
            <small>{{ shelter.area }} · 容量约 {{ shelter.capacity }} 人 · {{ shelter.contact }}</small>
          </div>
          <span>{{ shelter.source }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
