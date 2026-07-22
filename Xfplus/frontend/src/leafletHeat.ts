import * as L from 'leaflet'

let heatReady: Promise<typeof L> | null = null

export function ensureLeafletHeat() {
  if (!heatReady) {
    heatReady = (async () => {
      ;(window as typeof window & { L?: typeof L }).L = L
      if (!(L as any).heatLayer) {
        await import('leaflet.heat')
      }
      return L
    })()
  }
  return heatReady
}
