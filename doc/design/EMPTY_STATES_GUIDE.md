# Empty States Design Guide
## Actionable Guidance for Better UX

**Created:** 2026-04-18  
**Component:** `src/components/EmptyState.tsx`

---

## Overview

Empty states are critical UX moments. Instead of leaving users confused with "No results", we provide context, explanation, and clear next actions.

---

## Design Principles

### 1. Explain Why It's Empty
Never just say "No data". Tell users what's expected and why it's empty right now.

❌ **Bad:** "No results"  
✅ **Good:** "No forensic reports in the last 72 hours"

### 2. Suggest Next Action
Always provide at least one actionable path forward.

✅ **Examples:**
- "Check back tomorrow"
- "Browse all projects →"
- "Clear filters and try again"

### 3. Visual Interest
Use icons/emojis to make empty states friendly and less intimidating.

- ✅ Success/Stable: `icon="✅"`
- 🔍 Search/None found: `icon="🔍"`
- 📚 Library/Collection: `icon="📚"`
- 🎯 Goal/Target: `icon="🎯"`

### 4. Maintain Context
Users should understand where they are and what page functionality exists, even with no data.

---

## Component API

```tsx
<EmptyState
  icon="✅"                      // Optional emoji/icon
  title="No reports yet"        // Main heading (required)
  description="..."             // Explanation text (required)
  action={{                     // Primary CTA (optional)
    label: "Browse Reports",
    href: "/products"
  }}
  secondary={{                  // Secondary CTA (optional)
    label: "Contact Support",
    href: "/contact"
  }}
  variant="default"             // "default" | "success" | "info" | "search"
/>
```

---

## Usage Examples by Page

### 1. Reports Page (`/reports`)

**Scenario:** No FOR reports in 72-hour window

```tsx
<EmptyState
  icon="✅"
  title={locale === 'ko' 
    ? '현재 72시간 내 발행된 FOR 보고서가 없습니다'
    : 'No FOR reports published within the last 72 hours'}
  description={locale === 'ko'
    ? '시장이 안정적입니다. 급격한 가격 변동이 감지되면 여기에 새 포렌식 보고서가 표시됩니다.'
    : 'The market is stable. New forensic reports will appear here when rapid price movements are detected.'}
  action={{
    label: locale === 'ko' ? '모든 프로젝트 보기' : 'View All Projects',
    href: `/${locale}/products`
  }}
  secondary={{
    label: locale === 'ko' ? '뉴스레터 구독' : 'Subscribe to Alerts',
    href: `/${locale}/subscribe`
  }}
  variant="success"
/>
```

**When search returns no results:**

```tsx
{searchQuery && reports.length === 0 && (
  <EmptyState
    icon="🔍"
    title={locale === 'ko' 
      ? '검색 결과가 없습니다'
      : 'No results found'}
    description={locale === 'ko'
      ? `"${searchQuery}"와 일치하는 프로젝트를 찾을 수 없습니다. 다른 키워드로 시도해보세요.`
      : `No projects match "${searchQuery}". Try different keywords or browse all reports.`}
    action={{
      label: locale === 'ko' ? '필터 초기화' : 'Clear Filters',
      href: `/${locale}/reports`
    }}
    secondary={{
      label: locale === 'ko' ? '모든 보고서 보기' : 'Browse All Reports',
      href: `/${locale}/products`
    }}
    variant="search"
  />
)}
```

---

### 2. Score Page (`/score`)

**Scenario:** No tracked projects (rare, but possible)

```tsx
<EmptyState
  icon="📊"
  title={locale === 'ko' 
    ? '현재 추적 중인 프로젝트가 없습니다'
    : 'No projects currently tracked'}
  description={locale === 'ko'
    ? '곧 새로운 프로젝트가 추가될 예정입니다. 문의사항이 있으시면 연락주세요.'
    : 'We\'re adding new projects soon. Contact us if you have suggestions.'}
  action={{
    label: locale === 'ko' ? '문의하기' : 'Contact Us',
    href: `/${locale}/contact`
  }}
  secondary={{
    label: locale === 'ko' ? '보고서 둘러보기' : 'Browse Reports',
    href: `/${locale}/products`
  }}
  variant="info"
/>
```

---

### 3. Dashboard (`/dashboard`)

**Scenario A: Empty library (no purchased reports)**

```tsx
<EmptyState
  icon="📚"
  title={locale === 'ko' 
    ? '아직 보고서가 없습니다'
    : 'Your library is empty'}
  description={locale === 'ko'
    ? '연구 카탈로그를 둘러보고 첫 보고서를 구매하여 시작하세요.'
    : 'Browse our research catalog and purchase your first report to get started.'}
  action={{
    label: locale === 'ko' ? '보고서 둘러보기' : 'Browse Reports',
    href: `/${locale}/products`
  }}
  secondary={{
    label: locale === 'ko' ? '무료 샘플 보기' : 'View Free Samples',
    href: `/${locale}/free-reports`
  }}
  variant="default"
/>
```

**Scenario B: No order history**

```tsx
<EmptyState
  icon="🛒"
  title={locale === 'ko' 
    ? '주문 내역이 없습니다'
    : 'No orders yet'}
  description={locale === 'ko'
    ? '첫 보고서를 구매하면 주문 내역이 여기에 표시됩니다.'
    : 'Your order history will appear here once you make your first purchase.'}
  action={{
    label: locale === 'ko' ? '보고서 둘러보기' : 'Browse Reports',
    href: `/${locale}/products`
  }}
  variant="default"
/>
```

**Scenario C: No active subscriptions**

```tsx
<EmptyState
  icon="🔄"
  title={locale === 'ko' 
    ? '활성 구독이 없습니다'
    : 'No active subscriptions'}
  description={locale === 'ko'
    ? '구독 요금제로 업그레이드하여 무제한 액세스를 받으세요.'
    : 'Upgrade to a subscription plan for unlimited access to all research.'}
  action={{
    label: locale === 'ko' ? '요금제 보기' : 'View Plans',
    href: `/${locale}/products?filter=subscription`
  }}
  variant="info"
/>
```

---

### 4. Products Page (`/products`)

**Scenario:** Category filter returns no results

```tsx
<EmptyState
  icon="🎯"
  title={locale === 'ko' 
    ? '이 카테고리에 보고서가 없습니다'
    : 'No reports in this category'}
  description={locale === 'ko'
    ? '해당 카테고리에 아직 보고서가 없습니다. 다른 카테고리를 탐색해보세요.'
    : 'We don\'t have reports in this category yet. Explore other categories or check back soon.'}
  action={{
    label: locale === 'ko' ? '모든 카테고리 보기' : 'View All Categories',
    href: `/${locale}/products`
  }}
  variant="search"
/>
```

---

### 5. Free Reports Page (`/free-reports`)

**Scenario:** No free reports available (temporary)

```tsx
<EmptyState
  icon="🎁"
  title={locale === 'ko' 
    ? '현재 무료 샘플이 없습니다'
    : 'No free samples available'}
  description={locale === 'ko'
    ? '곧 새로운 무료 샘플을 추가할 예정입니다. 뉴스레터를 구독하여 알림을 받으세요.'
    : 'We\'re preparing new free samples. Subscribe to our newsletter to get notified.'}
  action={{
    label: locale === 'ko' ? '뉴스레터 구독' : 'Subscribe to Newsletter',
    href: `/${locale}/subscribe`
  }}
  secondary={{
    label: locale === 'ko' ? '프리미엄 보고서 보기' : 'View Premium Reports',
    href: `/${locale}/products`
  }}
  variant="info"
/>
```

---

### 6. Search Results (Global Search)

**Scenario:** Search query returns no results across all content

```tsx
<EmptyState
  icon="🔍"
  title={locale === 'ko' 
    ? `"${searchQuery}"에 대한 검색 결과가 없습니다`
    : `No results for "${searchQuery}"`}
  description={locale === 'ko'
    ? '검색어를 확인하거나 다른 키워드로 시도해보세요. 프로젝트명, 심볼, 카테고리로 검색할 수 있습니다.'
    : 'Check your spelling or try different keywords. You can search by project name, symbol, or category.'}
  action={{
    label: locale === 'ko' ? '검색 초기화' : 'Clear Search',
    href: window.location.pathname
  }}
  secondary={{
    label: locale === 'ko' ? '인기 프로젝트 보기' : 'View Popular Projects',
    href: `/${locale}/score`
  }}
  variant="search"
/>
```

---

## Visual Variants

### Default (Indigo)
For general empty states like empty library, no data.

```tsx
variant="default"
```

### Success (Green)
When empty state is actually a positive thing (stable market, no alerts).

```tsx
variant="success"
```

### Info (Blue)
For informational empty states (coming soon, feature in progress).

```tsx
variant="info"
```

### Search (Gray)
Specifically for "no results found" scenarios.

```tsx
variant="search"
```

---

## Accessibility Guidelines

1. **Semantic HTML**: Component uses proper `role="status"` and `aria-live="polite"`
2. **Icon hiding**: Decorative emojis use `aria-hidden="true"`
3. **Link text**: Action labels are descriptive without relying on visual context
4. **Keyboard navigation**: All CTAs are fully keyboard accessible
5. **Screen reader friendly**: Status message announces to screen readers

---

## Mobile Responsive

- **Icon size**: Scales from 64px (mobile) to 80px (desktop)
- **Button layout**: Stacks vertically on mobile, horizontal on desktop
- **Padding**: Reduces on smaller screens for better spacing
- **Text size**: Scales appropriately with viewport

---

## Implementation Checklist

When adding an empty state to a page:

- [ ] Import `EmptyState` component
- [ ] Determine appropriate icon (emoji or illustration)
- [ ] Write clear, contextual title (explain why it's empty)
- [ ] Write helpful description (what user should know/do)
- [ ] Add primary action (most relevant next step)
- [ ] Consider secondary action (alternative path)
- [ ] Choose appropriate variant (default/success/info/search)
- [ ] Test with screen reader
- [ ] Test on mobile devices
- [ ] Verify keyboard navigation works

---

## Testing Scenarios

To test empty states:

1. **Reports page**: Wait for > 72 hours with no new FOR reports
2. **Search**: Enter nonsense query string
3. **Dashboard**: Create new account with no purchases
4. **Products**: Apply category filter with no matching items
5. **Score**: Temporarily disable all tracked projects (admin)

---

## Related Components

- `DisclaimerBanner` - Informational banners
- `SubscribeForm` - Newsletter CTA integration
- `ProductCard` - When transitioning from empty to populated state

---

## Future Enhancements

### Phase 2 (Optional)
- [ ] Add illustration SVGs instead of emoji icons
- [ ] Animated transitions when data loads
- [ ] Contextual recommendations (similar to "you might also like")
- [ ] A/B test different CTA copy for conversion optimization

---

## Questions?

For UX decisions, consult:
- [BCE-440](/BCE/issues/BCE-440) - Original empty states task
- [BCE-438](/BCE/issues/BCE-438) - Accessibility audit reference

---

**End of Guide**
