import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const appDir = join(process.cwd(), 'src/app/[locale]/exchanges')

function readRouteSource(relativePath: string) {
  return readFileSync(join(appDir, relativePath), 'utf8')
}

function extractRgbaAlphas(source: string): number[] {
  return Array.from(source.matchAll(/rgba\([^)]*,\s*([01](?:\.\d+)?)\)/g), (match) => Number(match[1]))
}

function extractSlateOverlayOpacities(source: string): number[] {
  return Array.from(source.matchAll(/slate-950\/(\d+)/g), (match) => Number(match[1]))
}

describe('exchange page data contract', () => {
  it('keeps exchange pages aligned to the exchange listing repository', () => {
    const source = [
      readRouteSource('page.tsx'),
      readRouteSource('[slug]/page.tsx'),
    ].join('\n')

    expect(source).toContain('createExchangesRepository')
    expect(source).not.toContain('createProjectsRepository')
    expect(source).not.toContain('getExchangeProjectBySlug')
    expect(source).not.toContain("ilike('category'")
    expect(source).not.toContain('.ilike("category"')
    expect(source).toContain('BCE Exchange Score')
    expect(source).not.toContain('averageBceScore')
  })

  it('keeps exchange list and detail headers on the shared image-backed hero treatment', () => {
    const listSource = readRouteSource('page.tsx')
    const detailSource = readRouteSource('[slug]/page.tsx')

    expect(listSource).toContain("EXCHANGE_HEADER_BACKGROUND_IMAGE = '/images/exchange-header-bg.png'")
    expect(detailSource).toContain("EXCHANGE_HEADER_BACKGROUND_IMAGE = '/images/exchange-header-bg.png'")
    expect(listSource).toContain('data-testid="exchanges-hero"')
    expect(detailSource).toContain('data-testid="exchange-detail-hero"')
    expect(listSource).toContain('backgroundImage')
    expect(detailSource).toContain('backgroundImage')
  })

  it('does not hide exchange header images behind near-opaque dark overlays', () => {
    const source = [
      readRouteSource('page.tsx'),
      readRouteSource('[slug]/page.tsx'),
    ].join('\n')

    expect(Math.max(...extractRgbaAlphas(source))).toBeLessThanOrEqual(0.64)
    expect(Math.max(...extractSlateOverlayOpacities(source))).toBeLessThanOrEqual(25)
  })
})
