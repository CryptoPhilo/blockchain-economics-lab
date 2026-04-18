# Loading States Design Guide
## Consistent Loading UX Patterns

**Created:** 2026-04-18  
**Components:** `LoadingSkeleton`, `Spinner`, `ProgressBar`

---

## Overview

Loading states communicate system activity and maintain user engagement during data fetches, processing, or transitions. Consistent loading patterns reduce cognitive load and improve perceived performance.

---

## Core Principles

### 1. Never Show Blank Screens
Always provide visual feedback during loading. Users should understand the system is working.

❌ **Bad:** White/blank page while fetching data  
✅ **Good:** Skeleton screen showing content structure

### 2. Match Content Structure
Loading states should resemble the final content layout for visual continuity.

✅ **Examples:**
- Card grid → Show skeleton cards in grid layout
- Table → Show skeleton rows with table structure
- List → Show skeleton list items

### 3. Respect Accessibility
- Use ARIA attributes (`role="status"`, `aria-live="polite"`)
- Provide screen reader labels (`aria-label`, `.sr-only` text)
- Respect `prefers-reduced-motion` for animations

### 4. Optimize Perceived Performance
- Show content progressively (load critical content first)
- Use optimistic UI for actions with high success rates
- Set reasonable timeouts (>10s should show error state)

---

## Component Library

### 1. LoadingSkeleton

**Use for:** Lists, tables, cards, content blocks

```tsx
import LoadingSkeleton, { 
  CardSkeleton, 
  TableRowSkeleton, 
  ListSkeleton 
} from '@/components/LoadingSkeleton'

// Basic skeleton
<LoadingSkeleton variant="text" width="60%" height="20px" />

// Card grid skeleton
<CardSkeleton count={6} />

// Table rows skeleton
<TableRowSkeleton count={10} />

// List skeleton (reports page, etc.)
<ListSkeleton count={5} />

// Custom skeleton
<LoadingSkeleton 
  className="h-48 w-full rounded-xl"
  count={3}
/>
```

**Variants:**
- `card` - Full card skeleton (h-48)
- `table-row` - Table row skeleton (h-14)
- `text` - Text line skeleton (h-4)
- `avatar` - Avatar/icon skeleton (h-12 w-12 rounded-full)
- `custom` - Custom dimensions via className

---

### 2. Spinner

**Use for:** Button clicks, form submissions, small inline actions

```tsx
import Spinner, { 
  SpinnerOverlay, 
  ButtonSpinner 
} from '@/components/Spinner'

// Basic spinner
<Spinner size="md" variant="primary" label="Loading data" />

// In a button
<button disabled>
  <ButtonSpinner label="Submitting..." />
</button>

// Full-page overlay
<SpinnerOverlay label="Processing payment..." />
```

**Sizes:** `sm` (16px), `md` (32px), `lg` (48px), `xl` (64px)  
**Variants:** `primary` (indigo), `white`, `gray`

---

### 3. ProgressBar

**Use for:** Multi-step processes, file uploads, report generation

```tsx
import ProgressBar, { StepProgressBar } from '@/components/ProgressBar'

// Basic progress bar
<ProgressBar 
  progress={45} 
  label="Generating report..." 
  showPercentage 
  variant="primary"
/>

// Step progress bar
<StepProgressBar
  currentStep={2}
  totalSteps={4}
  steps={['Collect Data', 'Analyze', 'Generate PDF', 'Upload']}
/>
```

**Variants:** `primary` (indigo), `success` (green), `warning` (yellow), `danger` (red)  
**Sizes:** `sm` (8px), `md` (12px), `lg` (16px)

---

## Usage Patterns by Scenario

### 1. Page Load (Data Fetching)

**Scenario:** Score page loading top 200 projects

```tsx
export default function ScorePage() {
  const [loading, setLoading] = useState(true)
  const [projects, setProjects] = useState([])

  useEffect(() => {
    fetchProjects().then(data => {
      setProjects(data)
      setLoading(false)
    })
  }, [])

  if (loading) {
    return <TableRowSkeleton count={10} />
  }

  return (
    <div>
      {projects.map(project => <ProjectRow key={project.id} {...project} />)}
    </div>
  )
}
```

---

### 2. Infinite Scroll / Pagination

**Scenario:** Reports page with "Load More" button

```tsx
export default function ReportsPage() {
  const [loading, setLoading] = useState(false)
  const [reports, setReports] = useState([])
  const [hasMore, setHasMore] = useState(true)

  async function loadMore() {
    setLoading(true)
    const newReports = await fetchMoreReports()
    setReports([...reports, ...newReports])
    setHasMore(newReports.length > 0)
    setLoading(false)
  }

  return (
    <div>
      {reports.map(report => <ReportCard key={report.id} {...report} />)}
      
      {loading && <ListSkeleton count={3} />}
      
      {hasMore && !loading && (
        <button onClick={loadMore}>Load More</button>
      )}
    </div>
  )
}
```

---

### 3. Form Submission

**Scenario:** Newsletter subscription form

```tsx
export default function SubscribeForm() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setStatus('loading')
    
    try {
      await subscribeUser(email)
      setStatus('success')
    } catch {
      setStatus('error')
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input type="email" required />
      
      <button type="submit" disabled={status === 'loading'}>
        {status === 'loading' ? (
          <ButtonSpinner label="Subscribing..." />
        ) : (
          'Subscribe'
        )}
      </button>
    </form>
  )
}
```

---

### 4. Multi-Step Process

**Scenario:** Report generation pipeline

```tsx
export default function ReportGenerator() {
  const [currentStep, setCurrentStep] = useState(1)
  const steps = ['Collect Data', 'Analyze', 'Generate PDF', 'Upload']

  return (
    <div className="max-w-2xl mx-auto p-8">
      <StepProgressBar
        currentStep={currentStep}
        totalSteps={4}
        steps={steps}
      />

      <div className="mt-8">
        {currentStep === 1 && <DataCollectionStep />}
        {currentStep === 2 && <AnalysisStep />}
        {currentStep === 3 && <PDFGenerationStep />}
        {currentStep === 4 && <UploadStep />}
      </div>
    </div>
  )
}
```

---

### 5. Optimistic UI

**Scenario:** Like/favorite button (instant feedback, sync in background)

```tsx
export default function LikeButton({ reportId, initialLiked }: Props) {
  const [liked, setLiked] = useState(initialLiked)
  const [syncing, setSyncing] = useState(false)

  async function toggleLike() {
    // Optimistic update
    setLiked(!liked)
    setSyncing(true)

    try {
      await updateLikeStatus(reportId, !liked)
    } catch {
      // Revert on error
      setLiked(liked)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <button onClick={toggleLike} disabled={syncing}>
      {liked ? '❤️' : '🤍'}
      {syncing && <Spinner size="sm" className="ml-2" />}
    </button>
  )
}
```

---

### 6. Full-Page Loading

**Scenario:** Payment processing, critical server operations

```tsx
export default function CheckoutPage() {
  const [processing, setProcessing] = useState(false)

  async function handlePayment() {
    setProcessing(true)
    
    try {
      await processPayment()
      router.push('/success')
    } catch {
      alert('Payment failed')
    } finally {
      setProcessing(false)
    }
  }

  return (
    <>
      {processing && <SpinnerOverlay label="Processing payment..." />}
      
      <button onClick={handlePayment}>
        Pay Now
      </button>
    </>
  )
}
```

---

### 7. Timeout Handling

**Scenario:** Show error state if loading takes too long

```tsx
export default function DataPage() {
  const [status, setStatus] = useState<'loading' | 'loaded' | 'timeout'>('loading')

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (status === 'loading') {
        setStatus('timeout')
      }
    }, 10000) // 10 second timeout

    fetchData().then(() => {
      setStatus('loaded')
      clearTimeout(timeoutId)
    })

    return () => clearTimeout(timeoutId)
  }, [])

  if (status === 'loading') return <TableRowSkeleton count={10} />
  
  if (status === 'timeout') {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 mb-4">⚠️ Loading is taking longer than expected</p>
        <button onClick={() => window.location.reload()}>
          Reload Page
        </button>
      </div>
    )
  }

  return <DataTable />
}
```

---

## Accessibility Implementation

### 1. ARIA Attributes

All loading components include proper ARIA attributes:

```tsx
<div
  role="status"
  aria-live="polite"
  aria-label="Loading content"
>
  <span className="sr-only">Loading...</span>
  {/* visual spinner/skeleton */}
</div>
```

### 2. Screen Reader Announcements

```tsx
// Announce status changes
<div aria-live="polite" aria-atomic="true">
  {status === 'loading' && <span className="sr-only">Loading data...</span>}
  {status === 'success' && <span className="sr-only">Data loaded successfully</span>}
</div>
```

### 3. Reduced Motion Support

Add to `globals.css`:

```css
@media (prefers-reduced-motion: reduce) {
  .animate-spin,
  .animate-pulse {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Performance Best Practices

### 1. Progressive Loading

Load critical content first, defer secondary content:

```tsx
export default function ProductPage() {
  const [product, setProduct] = useState(null)
  const [reviews, setReviews] = useState(null)

  useEffect(() => {
    // Load product first (critical)
    fetchProduct().then(setProduct)
    
    // Defer reviews (secondary)
    setTimeout(() => {
      fetchReviews().then(setReviews)
    }, 500)
  }, [])

  return (
    <div>
      {product ? <ProductDetails {...product} /> : <CardSkeleton count={1} />}
      
      <h2>Reviews</h2>
      {reviews ? <ReviewList reviews={reviews} /> : <ListSkeleton count={3} />}
    </div>
  )
}
```

### 2. Skeleton Matching

Skeleton dimensions should match final content:

```tsx
// Product card: 320px height
<LoadingSkeleton className="h-80 w-full rounded-xl" />

// vs actual card
<div className="h-80 w-full rounded-xl bg-white/5">
  {/* content */}
</div>
```

### 3. Avoid Layout Shift

Reserve space for content to prevent cumulative layout shift (CLS):

```tsx
// Bad: content shifts when loaded
{loading ? <Spinner /> : <LargeContent />}

// Good: reserved space
<div className="min-h-[400px]">
  {loading ? <TableRowSkeleton count={10} /> : <DataTable />}
</div>
```

---

## Component Decision Matrix

| Scenario | Component | Example |
|----------|-----------|---------|
| Page load (list/table) | `LoadingSkeleton` | Reports page, Score page |
| Button click | `ButtonSpinner` | Form submit, Download button |
| Background action | `Spinner` (small) | Auto-save, Like button |
| Full-page block | `SpinnerOverlay` | Payment processing, Auth |
| Multi-step process | `ProgressBar` / `StepProgressBar` | Report generation, Onboarding |
| File upload | `ProgressBar` | Upload documents |
| Search/filter | `LoadingSkeleton` (inline) | Search results |

---

## Testing Checklist

- [ ] Loading state shows immediately on action
- [ ] Screen reader announces loading status
- [ ] Keyboard users can't interact with disabled elements
- [ ] Reduced motion users see non-animated version
- [ ] Timeout handling works (test with slow network)
- [ ] No layout shift when content loads
- [ ] Loading state matches final content structure
- [ ] Mobile responsive (test on small screens)

---

## Common Mistakes to Avoid

❌ **Don't:**
- Show generic "Loading..." text without context
- Use spinners for long-running operations (>3 seconds) without progress indication
- Forget to disable interactive elements during loading
- Let loading states persist indefinitely (always set timeouts)
- Ignore accessibility (ARIA attributes)

✅ **Do:**
- Match skeleton structure to final content
- Provide descriptive loading messages ("Generating report..." not just "Loading")
- Disable buttons/forms during submission
- Implement timeout and error states
- Test with screen readers

---

## Implementation Priority

### Phase 1: Critical (Immediate)
- [ ] Reports page skeleton
- [ ] Score page skeleton
- [ ] Form submission spinners (subscribe, auth)
- [ ] Button loading states

### Phase 2: Enhancement (Week 2)
- [ ] Dashboard skeletons (library, orders)
- [ ] Product page skeletons
- [ ] Search results loading
- [ ] Timeout error states

### Phase 3: Advanced (Future)
- [ ] Progress bars for report generation
- [ ] Step progress for onboarding
- [ ] Optimistic UI for likes/favorites
- [ ] Infinite scroll loading

---

## Related Files

- **Components:**
  - `src/components/LoadingSkeleton.tsx`
  - `src/components/Spinner.tsx`
  - `src/components/ProgressBar.tsx`
- **Styles:** `src/app/globals.css` (reduced motion media query)
- **Related Issues:**
  - [BCE-439](/BCE/issues/BCE-439) - Loading states implementation
  - [BCE-438](/BCE/issues/BCE-438) - Accessibility audit

---

## Examples in Codebase

After implementation, find examples here:

- **Reports Page:** `/app/[locale]/reports/page.tsx`
- **Score Page:** `/app/[locale]/score/page.tsx`
- **Subscribe Form:** `/components/SubscribeForm.tsx`
- **Dashboard:** `/app/[locale]/dashboard/page.tsx`

---

**End of Guide**
