import fs from 'fs'
import path from 'path'

describe('home page newsletter gate', () => {
  it('does not render the removed newsletter signup UI on the home page', () => {
    const source = fs.readFileSync(path.join(__dirname, 'page.tsx'), 'utf8')

    expect(source).not.toContain('SubscribeForm')
    expect(source).not.toContain('id="newsletter"')
    expect(source).not.toContain('home.freeNewsletter')
    expect(source).not.toContain('home.subscribeFree')
  })
})
