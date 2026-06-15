import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const appDir = join(process.cwd(), 'src/app/[locale]/exchanges')

function readRouteSource(relativePath: string) {
  return readFileSync(join(appDir, relativePath), 'utf8')
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
})
