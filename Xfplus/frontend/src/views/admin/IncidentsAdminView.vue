<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import WorkbenchBackButton from '../../components/WorkbenchBackButton.vue'
import { api } from '../../api'
import type { Incident, IncidentStatus } from '../../types'

const incidents = ref<Incident[]>([])
const statusFilter = ref('')
const typeFilter = ref('')
const notice = ref('')

const labels: Record<string, string> = {
  flood: '积水/山洪',
  landslide: '滑坡/落石',
  road: '道路中断',
  medical: '人员受伤',
  sos: 'SOS 求助',
  shelter: '安置需求',
  other: '其他',
}

const statusLabels: Record<string, string> = {
  pending: '待核实',
  responding: '处置中',
  resolved: '已完成',
}
const statusOrder: IncidentStatus[] = ['pending', 'responding', 'resolved']

function incidentPriority(incident: Incident) {
  return incident.type === 'sos' ? 1 : 0
}

function sortIncidents(items: Incident[]) {
  return [...items].sort((a, b) => {
    const priorityDiff = incidentPriority(b) - incidentPriority(a)
    if (priorityDiff) return priorityDiff
    const timeDiff = b.created_at.localeCompare(a.created_at)
    if (timeDiff) return timeDiff
    return b.id - a.id
  })
}

const groupedIncidents = computed(() =>
  statusOrder
    .map((status) => ({
      status,
      label: statusLabels[status],
      items: sortIncidents(incidents.value.filter((incident) => incident.status === status)),
    }))
    .filter((group) => group.items.length || !statusFilter.value),
)

function statusActions(incident: Incident) {
  return statusOrder.filter((status) => status !== incident.status)
}

async function selectStatusGroup(status: IncidentStatus) {
  statusFilter.value = statusFilter.value === status ? '' : status
  await load()
}

const timeline = computed(() => sortIncidents(incidents.value).slice(0, 10))

async function load() {
  const params: Record<string, string> = {}
  if (statusFilter.value) params.status = statusFilter.value
  if (typeFilter.value) params.type = typeFilter.value
  const { data } = await api.get('/api/incidents', { params })
  incidents.value = data.items || []
}

async function updateStatus(incident: Incident, status: IncidentStatus) {
  await api.put(`/api/incidents/${incident.id}/status`, { status })
  notice.value = `事件 #${incident.id} 已更新为 ${statusLabels[status]}${status === 'resolved' ? '，系统已通知上报人' : ''}`
  await load()
}

async function demoMode() {
  await api.post('/api/incidents/demo')
  notice.value = '演示事件已生成，事件处置列表和工作台地图均可查看。'
  await load()
}

onMounted(load)
</script>

<template>
  <section class="admin-page admin-page-full">
    <div class="admin-content">
      <div class="work-page-titlebar">
        <h1>事件管理</h1>
        <WorkbenchBackButton />
      </div>
      <p v-if="notice" class="notice">{{ notice }}</p>

      <article class="panel filter-panel">
        <label>
          处置状态
          <select v-model="statusFilter" @change="load">
            <option value="">全部</option>
            <option value="pending">待核实</option>
            <option value="responding">处置中</option>
            <option value="resolved">已完成</option>
          </select>
        </label>
        <label>
          事件类型
          <select v-model="typeFilter" @change="load">
            <option value="">全部</option>
            <option value="flood">积水/山洪</option>
            <option value="landslide">滑坡/落石</option>
            <option value="road">道路中断</option>
            <option value="medical">人员受伤</option>
            <option value="sos">SOS 求助</option>
            <option value="shelter">安置需求</option>
          </select>
        </label>
        <button @click="demoMode">一键生成演示事件</button>
      </article>

      <div class="admin-split">
        <article class="panel table-panel">
          <h2>处置列表</h2>
          <div class="incident-status-summary">
            <button
              v-for="group in groupedIncidents"
              :key="group.status"
              type="button"
              :class="['incident-status-chip', `status-${group.status}`, { active: statusFilter === group.status }]"
              @click="selectStatusGroup(group.status)"
            >
              {{ group.label }} {{ group.items.length }}
            </button>
          </div>

          <p v-if="!incidents.length" class="notice">暂无符合筛选条件的事件。</p>

          <section v-for="group in groupedIncidents" :key="group.status" class="incident-status-group">
            <div class="incident-group-head">
              <h3>{{ group.label }}</h3>
              <small>{{ group.items.length }} 件</small>
            </div>

            <div v-if="!group.items.length" class="incident-empty">当前分组暂无事件</div>

            <div v-for="incident in group.items" :key="incident.id" class="incident-admin-row">
              <div class="incident-main">
                <div class="incident-row-head">
                  <strong>#{{ incident.id }} {{ labels[incident.type] }}</strong>
                  <span :class="['incident-status-badge', `status-${incident.status}`]">{{ statusLabels[incident.status] }}</span>
                </div>
                <p>{{ incident.description }}</p>
                <small>{{ incident.district }} · {{ incident.scenic_area }} · {{ incident.created_at }}</small>
                <small v-if="incident.need_review">游客上报，需管理员审核</small>
                <small v-if="incident.nearest_shelter">
                  推荐安置点：{{ incident.nearest_shelter.name }}，约 {{ incident.nearest_shelter.distance_km }} km
                </small>
                <small v-if="incident.source_title" class="incident-source">
                  官方出处：
                  <a v-if="incident.source_url" :href="incident.source_url" target="_blank" rel="noreferrer">
                    {{ incident.source_org }} · {{ incident.source_title }} · {{ incident.source_date }}
                  </a>
                  <span v-else>{{ incident.source_org }} · {{ incident.source_title }} · {{ incident.source_date }}</span>
                </small>
                <ol v-if="incident.workflow_steps?.length" class="incident-workflow">
                  <li v-for="step in incident.workflow_steps" :key="step">{{ step }}</li>
                </ol>
              </div>
              <div class="status-stack">
                <button
                  v-for="status in statusActions(incident)"
                  :key="status"
                  :class="['status-action-button', { 'success-button': status === 'resolved', 'ghost-button': status === 'pending' }]"
                  @click="updateStatus(incident, status)"
                >
                  改为{{ statusLabels[status] }}
                </button>
              </div>
            </div>
          </section>
        </article>

        <article class="panel">
          <h2>事件时间线</h2>
          <div v-for="incident in timeline" :key="incident.id" class="timeline-item">
            <span>{{ incident.created_at }}</span>
            <strong>{{ labels[incident.type] }} · {{ statusLabels[incident.status] }}</strong>
            <p>{{ incident.description }}</p>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
