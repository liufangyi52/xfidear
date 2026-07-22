<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import WorkbenchBackButton from '../components/WorkbenchBackButton.vue'
import { api } from '../api'
import { loadSession } from '../auth'

const user = loadSession()
const districts = ['永定区', '武陵源区', '慈利县', '桑植县']
const data = ref<{ disaster_points: any[]; shelters: any[]; readonly: boolean }>({
  disaster_points: [],
  shelters: [],
  readonly: true,
})
const loading = ref(true)
const saving = ref(false)
const notice = ref('')
const locatingKind = ref<'risk' | 'shelter' | ''>('')

const fixedDistrict = computed(() => (user?.role === 'county_admin' ? user.district || '' : ''))
const canCreate = computed(() => user?.role === 'city_admin' || user?.role === 'county_admin')

type CoordinateKind = 'risk' | 'shelter' | 'both'

interface CoordinateCandidate {
  name: string
  lat: number
  lng: number
  district?: string
  location?: string
  kind: CoordinateKind
}

const coordinatePresets: CoordinateCandidate[] = [
  { name: '张家界大峡谷', lat: 29.3939, lng: 110.6938, district: '慈利县', location: '张家界大峡谷', kind: 'both' },
  { name: '大峡谷入口道路滑坡隐患点', lat: 29.3939, lng: 110.6938, district: '慈利县', location: '张家界大峡谷', kind: 'risk' },
  { name: '武陵源游客中心', lat: 29.3472, lng: 110.5587, district: '武陵源区', location: '武陵源游客中心', kind: 'shelter' },
  { name: '武陵源游客中心临时安置点', lat: 29.3472, lng: 110.5587, district: '武陵源区', location: '武陵源游客中心', kind: 'shelter' },
  { name: '天门山索道站', lat: 29.116, lng: 110.4749, district: '永定区', location: '天门山索道站', kind: 'both' },
  { name: '森林公园老磨湾游客中心', lat: 29.3342, lng: 110.4461, district: '武陵源区', location: '森林公园老磨湾游客中心', kind: 'shelter' },
  { name: '黄龙洞生态广场', lat: 29.361, lng: 110.6269, district: '武陵源区', location: '黄龙洞生态广场', kind: 'both' },
  { name: '金鞭溪', lat: 29.3472, lng: 110.5587, district: '武陵源区', location: '金鞭溪', kind: 'risk' },
]

const riskForm = reactive({
  name: '',
  district: fixedDistrict.value || '武陵源区',
  scenic_area: '',
  lat: '',
  lng: '',
  slope: '30',
  lithology: '现场补充录入',
  historical_landslide: '0',
})

const shelterForm = reactive({
  name: '',
  district: fixedDistrict.value || '武陵源区',
  location: '',
  lat: '',
  lng: '',
  capacity: '',
  contact: '区县应急值守',
})

onMounted(loadRiskData)

async function loadRiskData() {
  loading.value = true
  try {
    data.value = (await api.get('/api/risk-data')).data
  } finally {
    loading.value = false
  }
}

function activeDistrict(formDistrict: string) {
  return fixedDistrict.value || formDistrict
}

function numeric(value: string) {
  return Number(value)
}

function normalizeName(value: string) {
  return value.replace(/\s+/g, '').toLowerCase()
}

function coordinateText(value: number) {
  return value.toFixed(6)
}

function coordinateCandidates(kind: 'risk' | 'shelter') {
  const fromRisk = data.value.disaster_points.map((point) => ({
    name: point.name,
    lat: Number(point.lat),
    lng: Number(point.lng),
    district: point.district,
    location: point.scenic_area,
    kind: 'risk' as CoordinateKind,
  }))
  const fromShelters = data.value.shelters.map((shelter) => ({
    name: shelter.name,
    lat: Number(shelter.lat),
    lng: Number(shelter.lng),
    district: shelter.area,
    location: shelter.area,
    kind: 'shelter' as CoordinateKind,
  }))

  return [...coordinatePresets, ...fromRisk, ...fromShelters].filter((item) => {
    return item.kind === kind || item.kind === 'both'
  })
}

function matchCoordinate(kind: 'risk' | 'shelter', rawName: string) {
  const name = normalizeName(rawName)
  if (name.length < 2) return null

  return coordinateCandidates(kind).find((item) => {
    const candidates = [item.name, item.location || ''].map((value) => normalizeName(value)).filter(Boolean)
    return candidates.some((candidate) => name.includes(candidate) || candidate.includes(name))
  }) || null
}

function applyCoordinateMatch(kind: 'risk' | 'shelter', match: CoordinateCandidate) {
  if (kind === 'risk') {
    riskForm.lat = coordinateText(match.lat)
    riskForm.lng = coordinateText(match.lng)
    riskForm.scenic_area = riskForm.scenic_area || match.location || ''
    if (!fixedDistrict.value && match.district && districts.includes(match.district)) riskForm.district = match.district
    return
  }

  shelterForm.lat = coordinateText(match.lat)
  shelterForm.lng = coordinateText(match.lng)
  shelterForm.location = shelterForm.location || match.location || ''
  if (!fixedDistrict.value && match.district && districts.includes(match.district)) shelterForm.district = match.district
}

function applyGeocodedLocation(kind: 'risk' | 'shelter', location: any) {
  const lat = Number(location?.lat)
  const lng = Number(location?.lng)
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return

  if (kind === 'risk') {
    riskForm.lat = coordinateText(lat)
    riskForm.lng = coordinateText(lng)
    if (!fixedDistrict.value && location?.district && districts.includes(location.district)) riskForm.district = location.district
    return
  }

  shelterForm.lat = coordinateText(lat)
  shelterForm.lng = coordinateText(lng)
  if (!fixedDistrict.value && location?.district && districts.includes(location.district)) shelterForm.district = location.district
}

function clearCoordinates(kind: 'risk' | 'shelter') {
  if (kind === 'risk') {
    riskForm.lat = ''
    riskForm.lng = ''
    return
  }

  shelterForm.lat = ''
  shelterForm.lng = ''
}

async function fillCoordinatesByLocation(kind: 'risk' | 'shelter') {
  const location = kind === 'risk' ? riskForm.scenic_area.trim() : shelterForm.location.trim()
  if (!location) {
    notice.value = ''
    return
  }

  locatingKind.value = kind
  try {
    const response = await api.get('/api/map/geocode', {
      params: {
        q: location,
        district: activeDistrict(kind === 'risk' ? riskForm.district : shelterForm.district),
      },
    })
    notice.value = ''
    applyGeocodedLocation(kind, response.data)
  } catch {
    const match = matchCoordinate(kind, location)
    if (match) applyCoordinateMatch(kind, match)
    notice.value = ''
  } finally {
    locatingKind.value = ''
  }
}

function resetRiskForm() {
  riskForm.name = ''
  riskForm.district = fixedDistrict.value || riskForm.district
  riskForm.scenic_area = ''
  riskForm.lat = ''
  riskForm.lng = ''
  riskForm.slope = '30'
  riskForm.lithology = '现场补充录入'
  riskForm.historical_landslide = '0'
}

function resetShelterForm() {
  shelterForm.name = ''
  shelterForm.district = fixedDistrict.value || shelterForm.district
  shelterForm.location = ''
  shelterForm.lat = ''
  shelterForm.lng = ''
  shelterForm.capacity = ''
  shelterForm.contact = '区县应急值守'
}

async function submitRiskPoint() {
  if (!canCreate.value || saving.value) return
  saving.value = true
  notice.value = ''
  try {
    const payload = {
      kind: 'risk',
      risk: {
        ...riskForm,
        district: activeDistrict(riskForm.district),
        lat: numeric(riskForm.lat),
        lng: numeric(riskForm.lng),
        slope: numeric(riskForm.slope),
        historical_landslide: numeric(riskForm.historical_landslide),
      },
    }
    await api.post('/api/risk-data', payload)
    notice.value = '风险点已新增，工作台地图刷新后可见。'
    resetRiskForm()
    await loadRiskData()
  } catch (error: any) {
    notice.value = error?.response?.data?.detail || '新增失败，请检查点位字段和权限范围。'
  } finally {
    saving.value = false
  }
}

async function submitShelterPoint() {
  if (!canCreate.value || saving.value) return
  saving.value = true
  notice.value = ''
  try {
    const payload = {
      kind: 'shelter',
      shelter: {
        ...shelterForm,
        district: activeDistrict(shelterForm.district),
        lat: numeric(shelterForm.lat),
        lng: numeric(shelterForm.lng),
        capacity: numeric(shelterForm.capacity),
      },
    }
    await api.post('/api/risk-data', payload)
    notice.value = '安置点已新增，工作台地图刷新后可见。'
    resetShelterForm()
    await loadRiskData()
  } catch (error: any) {
    notice.value = error?.response?.data?.detail || '新增失败，请检查点位字段和权限范围。'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="page risk-data-page">
    <div class="work-page-titlebar">
      <h1>风险数据</h1>
      <WorkbenchBackButton />
    </div>

    <div class="risk-data-summary">
      <p class="hint">按现有字段新增地质灾害隐患点与安置点。新增后会进入风险数据，并在工作台地图刷新后显示。</p>
      <p v-if="loading" class="notice">正在加载风险数据...</p>
      <p v-if="notice" class="notice">{{ notice }}</p>
    </div>

    <section class="risk-data-workspace">
      <article class="panel risk-data-list-panel">
        <div class="risk-data-panel-head">
          <h2>地质灾害隐患点</h2>
        </div>

        <details v-if="canCreate" class="risk-data-create-details">
          <summary class="primary-button risk-data-add-toggle">新增点位</summary>
          <section class="risk-data-inline-create">
            <div class="risk-data-create-head">
              <h3>新增地质灾害隐患点</h3>
            </div>

            <form class="risk-data-form" @submit.prevent="submitRiskPoint">
              <label>
                点位名称
                <input v-model.trim="riskForm.name" required placeholder="如 大峡谷入口道路滑坡隐患点" />
              </label>
              <label>
                所属区县
                <select v-if="user?.role === 'city_admin'" v-model="riskForm.district" required>
                  <option v-for="district in districts" :key="district" :value="district">{{ district }}</option>
                </select>
                <input v-else :value="fixedDistrict" disabled />
              </label>
              <div class="risk-data-field">
                <span>景区/位置</span>
                <span class="risk-data-location-row">
                  <input
                    v-model.trim="riskForm.scenic_area"
                    required
                    placeholder="如 张家界大峡谷"
                    @input="clearCoordinates('risk')"
                  />
                  <button
                    class="risk-data-locate-button"
                    type="button"
                    :disabled="locatingKind === 'risk'"
                    @click.stop="fillCoordinatesByLocation('risk')"
                  >
                    {{ locatingKind === 'risk' ? '定位中' : '定位' }}
                  </button>
                </span>
              </div>
              <div class="risk-data-coordinate-row">
                <label>
                  纬度 lat
                  <input v-model="riskForm.lat" required inputmode="decimal" placeholder="如 29.393900" />
                </label>
                <label>
                  经度 lng
                  <input v-model="riskForm.lng" required inputmode="decimal" placeholder="如 110.693800" />
                </label>
              </div>
              <label>
                坡度
                <input v-model="riskForm.slope" required inputmode="decimal" />
              </label>
              <label>
                岩性/说明
                <input v-model.trim="riskForm.lithology" required />
              </label>
              <label>
                历史滑坡次数
                <input v-model="riskForm.historical_landslide" required inputmode="numeric" />
              </label>
              <button class="primary-button risk-data-submit" :disabled="saving">
                {{ saving ? '新增中...' : '新增风险点' }}
              </button>
            </form>
          </section>
        </details>

        <div v-for="point in data.disaster_points" :key="point.id" class="admin-row">
          <span class="dot orange" />
          <div>
            <strong>{{ point.name }}</strong>
            <small>{{ point.district }} · {{ point.scenic_area }} · 坡度 {{ point.slope }}</small>
            <small>{{ point.source }}</small>
          </div>
          <span class="risk-data-coords">{{ point.lat }}, {{ point.lng }}</span>
        </div>
      </article>

      <article class="panel risk-data-list-panel">
        <div class="risk-data-panel-head">
          <h2>安置点</h2>
        </div>

        <details v-if="canCreate" class="risk-data-create-details">
          <summary class="primary-button risk-data-add-toggle">新增点位</summary>
          <section class="risk-data-inline-create">
            <div class="risk-data-create-head">
              <h3>新增安置点</h3>
            </div>

            <form class="risk-data-form" @submit.prevent="submitShelterPoint">
              <label>
                点位名称
                <input v-model.trim="shelterForm.name" required placeholder="如 武陵源游客中心临时安置点" />
              </label>
              <label>
                所属区县
                <select v-if="user?.role === 'city_admin'" v-model="shelterForm.district" required>
                  <option v-for="district in districts" :key="district" :value="district">{{ district }}</option>
                </select>
                <input v-else :value="fixedDistrict" disabled />
              </label>
              <div class="risk-data-field">
                <span>景区/位置</span>
                <span class="risk-data-location-row">
                  <input
                    v-model.trim="shelterForm.location"
                    required
                    placeholder="如 武陵源游客中心"
                    @input="clearCoordinates('shelter')"
                  />
                  <button
                    class="risk-data-locate-button"
                    type="button"
                    :disabled="locatingKind === 'shelter'"
                    @click.stop="fillCoordinatesByLocation('shelter')"
                  >
                    {{ locatingKind === 'shelter' ? '定位中' : '定位' }}
                  </button>
                </span>
              </div>
              <div class="risk-data-coordinate-row">
                <label>
                  纬度 lat
                  <input v-model="shelterForm.lat" required inputmode="decimal" placeholder="如 29.347200" />
                </label>
                <label>
                  经度 lng
                  <input v-model="shelterForm.lng" required inputmode="decimal" placeholder="如 110.558700" />
                </label>
              </div>
              <label>
                安置容量
                <input v-model="shelterForm.capacity" required inputmode="numeric" placeholder="如 800" />
              </label>
              <label>
                联系方式
                <input v-model.trim="shelterForm.contact" required />
              </label>
              <button class="primary-button risk-data-submit" :disabled="saving">
                {{ saving ? '新增中...' : '新增安置点' }}
              </button>
            </form>
          </section>
        </details>

        <div v-for="shelter in data.shelters" :key="shelter.id" class="admin-row">
          <span class="dot blue" />
          <div>
            <strong>{{ shelter.name }}</strong>
            <small>{{ shelter.area }} · 容量约 {{ shelter.capacity }} 人 · {{ shelter.contact }}</small>
            <small>{{ shelter.source }}</small>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>
