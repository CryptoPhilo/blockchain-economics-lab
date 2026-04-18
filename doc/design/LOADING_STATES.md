# Loading States Design System

**Issue**: BCE-439  
**Date**: 2026-04-18  
**Status**: Implemented

## Overview

This document describes the consistent loading state system implemented across all pages in the BCE Lab application. The system uses Next.js `loading.tsx` files with Suspense boundaries and reusable skeleton components.

## Architecture

### Next.js Loading UI Pattern

We use Next.js 13+ App Router's automatic loading UI feature:

```
app/[locale]/
├── loading.tsx                    # Root loading (homepage)
├── products/
│   ├── loading.tsx               # Products list
│   └── [slug]/loading.tsx        # Product detail
├── projects/
│   ├── loading.tsx               # Projects list
│   └── [slug]/loading.tsx        # Project detail
├── reports/
│   ├── loading.tsx               # Reports list
│   └── forensic/[slug]/loading.tsx  # Forensic report detail
├── dashboard/loading.tsx          # User dashboard
├── score/loading.tsx              # Score table
├── free-reports/loading.tsx       # Free reports
├── contact/loading.tsx            # Contact form
└── auth/loading.tsx               # Authentication
```

### How It Works

1. **Automatic Suspense**: Next.js automatically wraps the page component in a Suspense boundary
2. **Instant UI**: Loading state shows immediately while async data fetches
3. **Streaming**: Page content streams in as it becomes available
4. **Route-level**: Each route segment can have its own loading state

## Component Library

### Core Components

Located in `src/components/`:

#### 1. `LoadingSkeleton.tsx`

Base skeleton component with variants:

```typescript
// Variants
- card: Full card skeleton (h-48)
- table-row: Table row skeleton (h-14)
- text: Text line skeleton (h-4)
- avatar: Avatar skeleton (h-12 w-12 rounded-full)
- custom: Custom dimensions

// Props
variant?: 'card' | 'table-row' | 'text' | 'avatar' | 'custom'
width?: string
height?: string
className?: string
count?: number  // Render multiple skeletons
```

**Specialized Exports**:
- `CardSkeleton`: Grid of card skeletons (for product/report cards)
- `TableRowSkeleton`: List of table row skeletons
- `ListSkeleton`: List of detailed item skeletons

#### 2. `Spinner.tsx`

Spinner component for in-page loading:

```typescript
// Variants
- primary: Indigo spinner (default)
- white: White spinner
- gray: Gray spinner

// Sizes
- sm: 4x4 with 2px border
- md: 8x8 with 2px border
- lg: 12x12 with 3px border
- xl: 16x16 with 4px border

// Props
size?: 'sm' | 'md' | 'lg' | 'xl'
variant?: 'primary' | 'white' | 'gray'
label?: string
className?: string
```

**Specialized Exports**:
- `SpinnerOverlay`: Full-screen overlay with spinner
- `ButtonSpinner`: Small spinner for button loading states

## Design Principles

### 1. Match Page Layout

Each loading state mirrors the expected page layout:

```typescript
// Example: Products page
- Header (title + description)
- Filter tabs
- Product grid (3 columns)

// Loading state matches this structure
- Header skeleton
- Filter skeleton
- CardSkeleton with count={6}
```

### 2. Consistent Animation

All skeletons use the same pulse animation:

```css
animate-pulse bg-gradient-to-r from-white/5 via-white/10 to-white/5
```

### 3. Accessibility

All loading components include:
- `role="status"`: Indicates loading region
- `aria-label="Loading content"`: Describes loading state
- `aria-live="polite"`: Announces completion to screen readers
- `<span className="sr-only">Loading...</span>`: Screen reader text

### 4. Color Consistency

Loading states use theme colors:
- Background: `bg-white/5` (subtle)
- Highlights: `bg-white/10` (more visible)
- Borders: `border-white/5`
- Branded: `bg-indigo-500/10` (for CTAs)

## Page-Specific Implementations

### Homepage (`[locale]/loading.tsx`)

**Structure**:
1. Hero section skeleton (gradient background)
2. Categories grid (5 items)
3. Featured products (CardSkeleton x4)

**Features**:
- Maintains gradient backgrounds
- Shows report type cards structure

### Products List (`products/loading.tsx`)

**Structure**:
1. Page header
2. Filter tabs (6 items)
3. Products grid (CardSkeleton x6)

**Grid**: Matches responsive grid (1/2/3 columns)

### Product Detail (`products/[slug]/loading.tsx`)

**Structure**:
1. Breadcrumb navigation
2. Product header (badges, title, description)
3. Pricing card
4. Content sections
5. Features grid

**Complexity**: Most detailed loading state with multiple sections

### Projects List (`projects/loading.tsx`)

**Structure**:
1. Page header
2. Search & filters
3. Stats cards (3 columns)
4. Projects list (ListSkeleton x6)

**Features**: Stats cards for metrics

### Project Detail (`projects/[slug]/loading.tsx`)

**Structure**:
1. Breadcrumb
2. Header with logo
3. Key metrics grid (4 items)
4. Tab navigation
5. Tab content (charts, tables)
6. Reports section

**Complexity**: Multiple data visualizations

### Reports List (`reports/loading.tsx`)

**Structure**:
1. Page header
2. Filter tabs (5 report types)
3. Search bar
4. Reports grid (CardSkeleton x9)

**Grid**: 3 columns to accommodate more reports

### Forensic Report Detail (`reports/forensic/[slug]/loading.tsx`)

**Structure**:
1. Breadcrumb
2. Report header
3. Key findings card
4. Report sections (5 sections with charts)
5. Risk assessment
6. Download actions
7. Related reports

**Features**: Specialized forensic report layout

### Dashboard (`dashboard/loading.tsx`)

**Structure**:
1. Welcome header
2. Stats cards (3 columns)
3. Tab navigation
4. Purchases list (ListSkeleton x4)
5. Referral section

**User-focused**: Personal stats and activities

### Score Table (`score/loading.tsx`)

**Structure**:
1. Page header
2. Score methodology card
3. Search & filters
4. Table header
5. Table rows (10 items)
6. Pagination

**Table-heavy**: Custom table row skeletons

### Free Reports (`free-reports/loading.tsx`)

**Structure**:
1. Page header
2. Lead magnet banner
3. Reports grid (CardSkeleton x6)

**Simple**: Similar to products but with lead gen focus

### Contact (`contact/loading.tsx`)

**Structure**:
1. Page header
2. Contact form (4 fields + submit)
3. Contact info cards (3 columns)

**Form-focused**: Field skeletons

### Auth (`auth/loading.tsx`)

**Structure**:
1. Logo
2. Auth card with tabs
3. Form fields
4. Submit button
5. Social login
6. Terms text

**Centered**: Full-height centered layout

## Usage Guidelines

### When to Use Loading States

1. **Route-level navigation**: Automatic with `loading.tsx`
2. **Data fetching delays**: Server components fetching from database
3. **Heavy computations**: Complex page rendering

### When to Use Spinners Instead

1. **Form submissions**: Use `ButtonSpinner`
2. **In-page actions**: Delete, update operations
3. **Modal content**: Loading within dialogs
4. **Infinite scroll**: Loading more items

### Best Practices

1. **Count accuracy**: Match skeleton count to typical data size
   - Featured products: 4
   - Product grid: 6-9
   - Table rows: 10
   - List items: 4-6

2. **Responsive grids**: Use same grid classes as actual content
   ```tsx
   grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3
   ```

3. **Maintain spacing**: Use same gap/padding as real content
   ```tsx
   space-y-8  // Match page sections
   gap-6      // Match grid gaps
   ```

4. **Color intensity**: Use lighter backgrounds for less important elements
   ```tsx
   bg-white/10  // Important (titles, prices)
   bg-white/5   // Secondary (descriptions, metadata)
   ```

## Performance Considerations

### Benefits

1. **Perceived performance**: Users see instant feedback
2. **Layout stability**: No layout shift when content loads
3. **Progressive enhancement**: Content streams in as available
4. **Reduced bounce**: Users wait longer with visual feedback

### Metrics

- **LCP improvement**: Skeleton renders immediately
- **CLS reduction**: Layout reserved before content loads
- **TTI**: Time to Interactive unaffected (non-blocking)

## Testing

### Manual Testing

1. **Slow 3G throttling**: Chrome DevTools → Network → Slow 3G
2. **Route navigation**: Click between pages to see transitions
3. **Hard refresh**: Cmd+Shift+R to see full page load
4. **Screen readers**: VoiceOver to test announcements

### Automated Testing

```typescript
// Test loading state renders
test('shows loading state', async () => {
  render(<Loading />)
  expect(screen.getByRole('status')).toBeInTheDocument()
  expect(screen.getByLabelText(/loading/i)).toBeInTheDocument()
})
```

## Maintenance

### Adding New Pages

1. Create `loading.tsx` in route folder
2. Analyze page structure
3. Use existing skeleton components
4. Match grid/spacing of actual page
5. Test with slow network

### Updating Existing

1. Keep loading state in sync with page changes
2. Update skeleton count if data size changes
3. Maintain responsive breakpoints
4. Test accessibility after changes

## Future Enhancements

### Potential Improvements

1. **Skeleton customization**: Theme-based skeleton colors
2. **Smart delays**: Show skeleton only after 200ms delay
3. **Error states**: Add error boundaries with retry
4. **Partial loading**: Stream sections independently
5. **Animated transitions**: Fade-in when content loads

### Accessibility Enhancements

1. **Reduced motion**: Respect `prefers-reduced-motion`
2. **Better announcements**: More descriptive loading messages
3. **Progress indicators**: Show loading percentage for known durations
4. **Keyboard focus**: Manage focus when content appears

## References

- [Next.js Loading UI](https://nextjs.org/docs/app/building-your-application/routing/loading-ui-and-streaming)
- [React Suspense](https://react.dev/reference/react/Suspense)
- [Skeleton Screens](https://www.nngroup.com/articles/skeleton-screens/)
- [WCAG Loading States](https://www.w3.org/WAI/WCAG21/Understanding/status-messages.html)
