# Accessibility Testing Checklist
## BCE Lab WCAG 2.1 AA Validation Guide

**Purpose:** Manual testing checklist for validating accessibility fixes  
**Scope:** Phase 1 Critical Fixes (BCE-445)  
**Updated:** 2026-04-18  
**Owner:** UXDesigner

---

## Testing Tools Required

### Browser Extensions
- [ ] **axe DevTools** - Automated accessibility testing
- [ ] **WAVE** - Visual accessibility feedback
- [ ] **Lighthouse** - Chrome DevTools audit

### Screen Readers
- [ ] **NVDA** (Windows - free)
- [ ] **JAWS** (Windows - trial available)
- [ ] **VoiceOver** (macOS - built-in)
- [ ] **TalkBack** (Android - built-in)

### Other Tools
- [ ] Keyboard only (unplug mouse)
- [ ] Colorblind simulator (Chrome extension)
- [ ] Zoom testing (browser zoom to 200%)

---

## Phase 1: Critical Fixes Validation

### ✅ Test 1: Skip Navigation Link
**WCAG:** 2.4.1 Bypass Blocks (Level A)  
**File:** `src/components/Header.tsx`

**Test Steps:**
1. Load any page
2. Press `Tab` key (first tab should focus skip link)
3. Verify skip link becomes visible on focus
4. Press `Enter` on skip link
5. Verify focus moves to main content area

**Pass Criteria:**
- [ ] Skip link is first tabbable element
- [ ] Skip link visible when focused (not hidden)
- [ ] Activating skip link moves focus to `#main-content`
- [ ] Skip link has clear text (e.g., "Skip to main content")
- [ ] Skip link styling matches brand (indigo theme)

**Screen Reader:**
- [ ] NVDA announces "Skip to main content, link"
- [ ] VoiceOver announces skip link clearly

---

### ✅ Test 2: Language Dropdown Keyboard Accessibility
**WCAG:** 2.1.1 Keyboard (Level A)  
**File:** `src/components/Header.tsx`

**Test Steps:**
1. Navigate to language dropdown with `Tab`
2. Press `Enter` or `Space` to open dropdown
3. Use arrow keys to navigate languages
4. Press `Enter` to select
5. Press `Escape` to close without selecting

**Pass Criteria:**
- [ ] Dropdown opens with `Enter` or `Space`
- [ ] Arrow keys navigate options
- [ ] `Escape` closes dropdown
- [ ] Focus returns to trigger button on close
- [ ] Selected language visually indicated
- [ ] Focus trapped within dropdown when open

**Screen Reader:**
- [ ] Announces current language
- [ ] Announces total options count
- [ ] Announces each option as navigated

**Alternative (if using native `<select>`):**
- [ ] Native `<select>` works with keyboard
- [ ] Options navigable with arrow keys
- [ ] Selection works with `Enter`

---

### ✅ Test 3: Mobile Menu Toggle ARIA
**WCAG:** 4.1.2 Name, Role, Value (Level A)  
**File:** `src/components/Header.tsx`

**Test Steps:**
1. Resize browser to mobile width (<768px)
2. Tab to mobile menu button
3. Verify button label
4. Activate button
5. Verify menu state announcement

**Pass Criteria:**
- [ ] Button has `aria-label="Toggle navigation menu"` (or similar)
- [ ] Button has `aria-expanded` attribute
- [ ] `aria-expanded="false"` when closed
- [ ] `aria-expanded="true"` when open
- [ ] Button has `aria-controls` pointing to menu ID
- [ ] Mobile nav has matching `id`

**Screen Reader:**
- [ ] NVDA announces "Toggle navigation menu, button, collapsed/expanded"
- [ ] State change announced when toggled

**Visual:**
- [ ] Icon changes clearly (hamburger ↔ X)
- [ ] Focus indicator visible

---

### ✅ Test 4: Form Labels
**WCAG:** 3.3.2 Labels, 1.3.1 Info and Relationships (Level A)  
**Files:** All forms (subscribe, auth, etc.)

**Test Steps - Subscribe Form:**
1. Navigate to subscribe form
2. Tab to email input
3. Verify label association
4. Submit empty form (error state)

**Pass Criteria:**
- [ ] Every input has associated `<label>` element
- [ ] `<label>` has `for` attribute matching input `id`
- [ ] Label text descriptive (not just placeholder)
- [ ] Error messages have `aria-describedby` on input
- [ ] Required fields marked with `aria-required="true"`

**Screen Reader:**
- [ ] Focus on input announces label text
- [ ] Announces "required" if applicable
- [ ] Error messages announced on blur/submit

**Pages to Check:**
- [ ] `/subscribe` - email form
- [ ] `/auth` - login/signup forms
- [ ] `/dashboard` - search/filter inputs
- [ ] `/reports` - search input

---

### ✅ Test 5: SVG Icon Accessible Text
**WCAG:** 1.1.1 Non-text Content (Level A)  
**File:** `src/components/Header.tsx:98-103`

**Test Steps:**
1. Navigate to mobile menu toggle
2. Verify SVG has accessible label
3. Test with screen reader

**Pass Criteria:**
- [ ] SVG has `aria-label` attribute
- [ ] Label describes icon purpose
- [ ] Label updates based on state (open/close)
- [ ] Decorative icons have `aria-hidden="true"`

**Screen Reader:**
- [ ] Icon purpose announced (e.g., "Close menu icon")
- [ ] Decorative icons not announced

---

### ✅ Test 6: Focus Indicators
**WCAG:** 2.4.7 Focus Visible (Level AA)  
**File:** `src/app/globals.css`

**Test Steps:**
1. Navigate entire site with keyboard only
2. Tab through all interactive elements
3. Verify focus indicator on each

**Pass Criteria:**
- [ ] All links show focus indicator
- [ ] All buttons show focus indicator
- [ ] All form inputs show focus indicator
- [ ] Focus indicator has 3:1 contrast ratio
- [ ] Focus indicator 2px minimum thickness
- [ ] Indicator visible against all backgrounds

**Elements to Check:**
- [ ] Header navigation links
- [ ] Language dropdown
- [ ] Sign In button
- [ ] Mobile menu toggle
- [ ] Footer links
- [ ] Report download buttons
- [ ] Search inputs
- [ ] Pagination links

**Style Requirements:**
```css
*:focus-visible {
  outline: 2px solid #6366f1; /* indigo-500 */
  outline-offset: 2px;
}
```

---

### ✅ Test 7: [Critical Issue 7]
**To be specified from full audit report**

---

### ✅ Test 8: [Critical Issue 8]
**To be specified from full audit report**

---

## Automated Testing

### axe DevTools Scan
1. Install axe DevTools Chrome extension
2. Open DevTools → axe tab
3. Click "Scan ALL of my page"
4. Review violations

**Pass Criteria:**
- [ ] 0 critical violations
- [ ] 0 serious violations
- [ ] Document moderate/minor for Phase 2

### Lighthouse Audit
1. Open Chrome DevTools → Lighthouse
2. Select "Accessibility" category
3. Generate report

**Pass Criteria:**
- [ ] Accessibility score ≥ 90
- [ ] All critical issues resolved
- [ ] Document remaining issues

### WAVE Extension
1. Install WAVE extension
2. Click WAVE icon on each page
3. Review errors/alerts

**Pass Criteria:**
- [ ] 0 errors on main pages
- [ ] Alerts reviewed and documented

---

## Browser/Device Testing Matrix

### Desktop Browsers
- [ ] Chrome (latest) + NVDA
- [ ] Firefox (latest) + NVDA
- [ ] Safari (latest) + VoiceOver
- [ ] Edge (latest)

### Mobile Devices
- [ ] iOS Safari + VoiceOver
- [ ] Android Chrome + TalkBack

### Keyboard Patterns
- [ ] Tab (forward navigation)
- [ ] Shift+Tab (backward navigation)
- [ ] Enter (activate)
- [ ] Space (activate checkboxes/buttons)
- [ ] Escape (close modals/dropdowns)
- [ ] Arrow keys (navigate menus/options)

---

## Testing Workflow

### Pre-Implementation
1. Document baseline issues (done in BCE-438)
2. Create this testing checklist
3. Set up testing tools

### During Implementation
1. Developer implements fix
2. Developer runs basic keyboard test
3. Developer runs axe DevTools

### Post-Implementation (UX Designer)
1. **Manual Keyboard Testing** (30 min)
   - Test all interactive elements
   - Verify focus indicators
   - Check tab order logic

2. **Screen Reader Testing** (45 min)
   - Test with NVDA (Windows)
   - Test with VoiceOver (macOS)
   - Verify all announcements

3. **Automated Scan** (15 min)
   - Run axe DevTools
   - Run Lighthouse
   - Run WAVE

4. **Mobile Testing** (30 min)
   - Test on real iOS device
   - Test on real Android device
   - Verify touch targets ≥44px

5. **Documentation** (15 min)
   - Fill out this checklist
   - Screenshot any issues
   - Create follow-up tasks if needed

**Total Validation Time:** ~2.5 hours

---

## Regression Testing

After fixes, verify we didn't break anything:
- [ ] All pages still load correctly
- [ ] Visual design unchanged (except focus indicators)
- [ ] Functionality intact (forms submit, navigation works)
- [ ] No console errors
- [ ] Mobile responsive still works

---

## Sign-Off

### Implementation Complete
- **Developer:** _______________
- **Date:** _______________
- **Commit SHA:** _______________

### Validation Complete
- **UX Designer:** _______________
- **Date:** _______________
- **Test Results:** Pass / Fail / Conditional
- **Notes:**

---

## Next Steps After Phase 1

Once Phase 1 passes:
1. Create Phase 2 implementation task (12 high-priority issues)
2. Create Phase 3 implementation task (9 medium-priority issues)
3. Schedule ongoing accessibility audits (quarterly)
4. Train team on accessible development practices

---

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [axe DevTools](https://www.deque.com/axe/devtools/)
- [NVDA Screen Reader](https://www.nvaccess.org/download/)
- [WebAIM Keyboard Testing](https://webaim.org/articles/keyboard/)
- [Color Contrast Checker](https://webaim.org/resources/contrastchecker/)
