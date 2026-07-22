<script setup lang="ts">
import { onMounted, ref } from 'vue'
import WorkbenchBackButton from '../../components/WorkbenchBackButton.vue'
import { api } from '../../api'
import type { Alert } from '../../types'

const alerts = ref<Alert[]>([])
const selectedId = ref<number | null>(null)
const report = ref('')
const reportEdited = ref(false)
const notice = ref('')
const generating = ref(false)
const aiGeneratedLabel = '复盘报告由AI生成'

onMounted(async () => {
  alerts.value = (await api.get('/api/alerts')).data
  selectedId.value = alerts.value[0]?.id || null
})

async function generate() {
  if (!selectedId.value || generating.value) return
  generating.value = true
  const startedAt = performance.now()
  notice.value = 'AI 正在调用 DeepSeek，结合预警事件和推送记录生成复盘报告...'
  try {
    const { data } = await api.post('/api/generate_postmortem', { alert_id: selectedId.value })
    report.value = sanitizeReportText(data.text)
    reportEdited.value = false
    const seconds = Math.max(1, Math.round((performance.now() - startedAt) / 1000))
    notice.value = data.fallback_used
      ? `复盘已生成，用时约 ${seconds} 秒。当前 AI 使用备用模式（${data.llm_provider}），回答质量可能有波动`
      : `复盘已生成，用时约 ${seconds} 秒，当前使用 ${data.llm_provider}`
  } catch (error: any) {
    notice.value = error?.response?.data?.detail || 'AI 复盘生成失败，请稍后重试。'
  } finally {
    generating.value = false
  }
}

function selectedAlertTitle() {
  return alerts.value.find((item) => item.id === selectedId.value)?.title || '复盘报告'
}

function safeFilename(name: string) {
  return name.replace(/[\\/:*?"<>|]/g, '_').slice(0, 80)
}

function markReportEdited() {
  if (report.value) {
    reportEdited.value = true
  }
}

function sanitizeReportText(value: string) {
  const selectedTitle = selectedAlertTitle()
  const titleCandidates = new Set([
    selectedTitle,
    `${selectedTitle}复盘报告`,
    `${selectedTitle}复盘报告。`,
    `【${selectedTitle}】复盘报告`,
    `《${selectedTitle}》复盘报告`,
  ])
  const cleanedLines = String(value || '')
    .replace(/\r/g, '')
    .split('\n')
    .map((line) =>
      line
        .replace(/^[\s#>*-]+/, '')
        .replace(/\*/g, '')
        .replace(/#{1,6}/g, '')
        .trim()
    )
    .filter((line) => {
      if (!line) return false
      if (titleCandidates.has(line)) return false
      if (/^好的[，,]/.test(line)) return false
      if (/^根据.*生成.*复盘报告[。.]?$/.test(line)) return false
      if (/^现为您.*复盘报告[。.]?$/.test(line)) return false
      return true
    })
  return cleanedLines.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

function escapeHtml(value: string) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
}

function downloadBlob(content: BlobPart, filename: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function downloadMarkdown() {
  if (!report.value) return
  downloadBlob(`\ufeff${report.value}`, `${safeFilename(selectedAlertTitle())}-复盘报告.md`, 'text/markdown;charset=utf-8')
  notice.value = 'Markdown 文件已开始下载。'
}

function downloadWord() {
  if (!report.value) return
  const title = `${selectedAlertTitle()}复盘报告`
  const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(title)}</title>
  <style>
    body { font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.7; color: #172033; padding: 24px; }
    h1 { font-size: 24px; margin: 0 0 20px; }
    pre { font: inherit; white-space: pre-wrap; word-break: break-word; }
  </style>
</head>
<body>
  <h1>${escapeHtml(title)}</h1>
  <pre>${escapeHtml(report.value)}</pre>
</body>
</html>`
  downloadBlob(`\ufeff${html}`, `${safeFilename(selectedAlertTitle())}-复盘报告.doc`, 'application/msword;charset=utf-8')
  notice.value = 'Word 文件已开始下载。'
}

function dataUrlToBytes(dataUrl: string) {
  const base64 = dataUrl.split(',')[1] || ''
  const binary = window.atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes
}

function concatBytes(chunks: Uint8Array[]) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const output = new Uint8Array(totalLength)
  let offset = 0
  chunks.forEach((chunk) => {
    output.set(chunk, offset)
    offset += chunk.length
  })
  return output
}

function wrapCanvasText(context: CanvasRenderingContext2D, text: string, maxWidth: number) {
  const rows: string[] = []
  text.split(/\r?\n/).forEach((paragraph) => {
    if (!paragraph) {
      rows.push('')
      return
    }
    let current = ''
    Array.from(paragraph).forEach((char) => {
      const next = current + char
      if (current && context.measureText(next).width > maxWidth) {
        rows.push(current)
        current = char
      } else {
        current = next
      }
    })
    rows.push(current)
  })
  return rows
}

function renderReportPages() {
  const pageWidth = 1240
  const pageHeight = 1754
  const margin = 86
  const title = `${selectedAlertTitle()}复盘报告`
  const generatedAt = new Date().toLocaleString('zh-CN', { hour12: false })
  const pages: { dataUrl: string; width: number; height: number }[] = []
  let canvas = document.createElement('canvas')
  let context = canvas.getContext('2d')
  let y = margin
  let pageNumber = 0

  const setupPage = () => {
    canvas = document.createElement('canvas')
    canvas.width = pageWidth
    canvas.height = pageHeight
    context = canvas.getContext('2d')
    if (!context) throw new Error('PDF 画布初始化失败')
    pageNumber += 1
    context.fillStyle = '#ffffff'
    context.fillRect(0, 0, pageWidth, pageHeight)
    context.fillStyle = '#172033'
    context.font = '700 42px "Microsoft YaHei", Arial, sans-serif'
    context.fillText(title, margin, y)
    y += 58
    context.font = '24px "Microsoft YaHei", Arial, sans-serif'
    context.fillStyle = '#5f6b7a'
    context.fillText(`生成时间：${generatedAt}    第 ${pageNumber} 页`, margin, y)
    y += 58
    context.strokeStyle = '#d8e2ea'
    context.lineWidth = 2
    context.beginPath()
    context.moveTo(margin, y)
    context.lineTo(pageWidth - margin, y)
    context.stroke()
    y += 52
    context.font = '28px "Microsoft YaHei", Arial, sans-serif'
    context.fillStyle = '#172033'
  }

  const finishPage = () => {
    if (!context) return
    pages.push({ dataUrl: canvas.toDataURL('image/jpeg', 0.92), width: pageWidth, height: pageHeight })
  }

  setupPage()
  if (!context) return pages
  const lines = wrapCanvasText(context, report.value, pageWidth - margin * 2)
  lines.forEach((line) => {
    if (!context) return
    if (y + 44 > pageHeight - margin) {
      finishPage()
      y = margin
      setupPage()
    }
    context.fillText(line || ' ', margin, y)
    y += line ? 44 : 32
  })
  finishPage()
  return pages
}

function buildPdfFromPages(pages: { dataUrl: string; width: number; height: number }[]) {
  const encoder = new TextEncoder()
  const encode = (value: string) => encoder.encode(value)
  const pdfWidth = 595.28
  const pdfHeight = 841.89
  const objects: Uint8Array[][] = []
  const pageRefs = pages.map((_, index) => `${3 + index * 3} 0 R`).join(' ')

  objects[1] = [encode('<< /Type /Catalog /Pages 2 0 R >>')]
  objects[2] = [encode(`<< /Type /Pages /Kids [${pageRefs}] /Count ${pages.length} >>`)]

  pages.forEach((page, index) => {
    const pageObjectId = 3 + index * 3
    const contentObjectId = pageObjectId + 1
    const imageObjectId = pageObjectId + 2
    const imageName = `Im${index + 1}`
    const content = encode(`q\n${pdfWidth} 0 0 ${pdfHeight} 0 0 cm\n/${imageName} Do\nQ\n`)
    const image = dataUrlToBytes(page.dataUrl)

    objects[pageObjectId] = [
      encode(
        `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pdfWidth} ${pdfHeight}] /Resources << /XObject << /${imageName} ${imageObjectId} 0 R >> >> /Contents ${contentObjectId} 0 R >>`
      )
    ]
    objects[contentObjectId] = [encode(`<< /Length ${content.length} >>\nstream\n`), content, encode('\nendstream')]
    objects[imageObjectId] = [
      encode(
        `<< /Type /XObject /Subtype /Image /Width ${page.width} /Height ${page.height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${image.length} >>\nstream\n`
      ),
      image,
      encode('\nendstream')
    ]
  })

  const header = encode('%PDF-1.4\n')
  const chunks: Uint8Array[] = [header]
  const offsets: number[] = []
  let position = header.length
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = position
    const objectBytes = concatBytes([encode(`${id} 0 obj\n`), ...objects[id]!, encode('\nendobj\n')])
    chunks.push(objectBytes)
    position += objectBytes.length
  }
  const xrefStart = position
  const xrefRows = ['xref', `0 ${objects.length}`, '0000000000 65535 f ']
  for (let id = 1; id < objects.length; id += 1) {
    xrefRows.push(`${String(offsets[id]).padStart(10, '0')} 00000 n `)
  }
  chunks.push(
    encode(`${xrefRows.join('\n')}\ntrailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF`)
  )
  return concatBytes(chunks)
}

function downloadPdf() {
  if (!report.value) return
  try {
    const pages = renderReportPages()
    const pdfBytes = buildPdfFromPages(pages)
    downloadBlob(pdfBytes, `${safeFilename(selectedAlertTitle())}-复盘报告.pdf`, 'application/pdf')
    notice.value = 'PDF 文件已开始下载。'
  } catch (error) {
    notice.value = 'PDF 生成失败，请稍后重试或先下载 Word 文件。'
  }
}
</script>

<template>
  <section class="admin-page admin-page-full">
    <div class="admin-content">
      <div class="work-page-titlebar">
        <h1>复盘报告</h1>
        <WorkbenchBackButton />
      </div>
      <p v-if="notice" class="notice">{{ notice }}</p>
      <div class="panel report-panel">
        <select v-model="selectedId" :disabled="generating">
          <option v-for="alert in alerts" :key="alert.id" :value="alert.id">{{ alert.title }}</option>
        </select>
        <div class="report-actions">
          <button type="button" class="primary-button ai-generate-button" :disabled="generating || !selectedId" @click="generate">
            <span v-if="generating" class="button-spinner light" aria-hidden="true"></span>
            {{ generating ? '生成复盘中...' : 'AI 生成复盘报告' }}
          </button>
          <button type="button" class="ghost-button" :disabled="!report" @click="downloadWord">Word 下载</button>
          <button type="button" class="ghost-button" :disabled="!report" @click="downloadMarkdown">Markdown 下载</button>
          <button type="button" class="ghost-button" :disabled="!report" @click="downloadPdf">PDF 下载</button>
        </div>
        <p v-if="generating" class="hint report-generate-hint">正在读取预警、播报和推送记录，请稍候。</p>
        <div v-if="report" class="report-editor-wrap">
          <div class="report-ai-badge">{{ aiGeneratedLabel }}</div>
          <div class="report-editor-meta">
            <span>{{ reportEdited ? '已手动修改，下载将使用当前内容' : '可直接编辑 AI 生成内容' }}</span>
            <span>{{ report.length }} 字</span>
          </div>
          <textarea
            v-model="report"
            class="report-editor role-text"
            aria-label="复盘报告内容"
            spellcheck="false"
            @input="markReportEdited"
          ></textarea>
        </div>
      </div>
    </div>
  </section>
</template>
