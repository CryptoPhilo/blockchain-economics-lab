import { enhanceSlideViewerHtmlForEmbed } from './SlideViewer'

describe('enhanceSlideViewerHtmlForEmbed', () => {
  const baseHtml = `<!DOCTYPE html>
<html>
<head>
<style>
.viewer-container { width: 90vw; }
</style>
</head>
<body>
<div class="viewer-container" id="viewer">
  <div class="title-bar">Title</div>
  <div class="slide-wrapper"></div>
  <div class="controls"></div>
</div>
<script>
// Load first slide
</script>
</body>
</html>`

  it('patches legacy slide HTML with fullscreen overlay chrome behavior', () => {
    const html = enhanceSlideViewerHtmlForEmbed(baseHtml)

    expect(html).toContain('body class="bcelab-slide-viewer-embed"')
    expect(html).toContain('data-bcelab-fullscreen-overlay="true"')
    expect(html).toContain('body.bcelab-parent-fullscreen .title-bar')
    expect(html).toContain('body.bcelab-parent-fullscreen .slide-wrapper')
    expect(html).toContain('height: 100vh')
    expect(html).toContain('bcelab-slide-viewer-fullscreen-state')
    expect(html).toContain('bcelab-slide-viewer-interaction')
    expect(html).toContain('bcelabFullscreenOverlayInstalled')
  })

  it('does not hide chrome for regular embedded views unless fullscreen is active', () => {
    const html = enhanceSlideViewerHtmlForEmbed(baseHtml)

    expect(html).not.toContain('body.bcelab-slide-viewer-embed .title-bar')
    expect(html).not.toContain('body.bcelab-slide-viewer-embed .controls')
  })

  it('is idempotent once the slide HTML is patched', () => {
    const once = enhanceSlideViewerHtmlForEmbed(baseHtml)
    const twice = enhanceSlideViewerHtmlForEmbed(once)

    expect(twice).toBe(once)
    expect((twice.match(/bcelab-slide-viewer-interaction/g) ?? []).length).toBe(1)
  })
})
