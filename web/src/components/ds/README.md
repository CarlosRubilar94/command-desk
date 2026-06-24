# Command Desk — Design System (`ds/`)

Dark-console design system primitives for Command Desk. Built on Tailwind CSS v4 + existing `--dsd-*` tokens. **No new npm dependencies.**

---

## Token Reference (`web/src/devssd-tokens.css`)

All tokens live under `:root` and are consumed via `var(--dsd-*)`. Original tokens are preserved; semantic aliases are added.

| Category | Key tokens |
|---|---|
| **Background layers** | `--dsd-layer-app`, `--dsd-layer-surface`, `--dsd-layer-raised`, `--dsd-layer-overlay` |
| **Borders** | `--dsd-border-default`, `--dsd-border-emphasis`, `--dsd-border-focus` |
| **Text** | `--dsd-text-base`, `--dsd-text-dim`, `--dsd-text-faint`, `--dsd-text-accent` |
| **Accent** | `--dsd-accent-primary` (cyan), `--dsd-accent-secondary` (violet), `--dsd-accent-tertiary` (emerald) |
| **Status** | `--dsd-status-{success/warning/error/info/neutral/degraded}` + `-bg` variants |
| **Agent categories** | `--dsd-cat-{agent/mission/tool/model/cost/fleet/trace}` |
| **Spacing** | `--dsd-space-{1–16}` (4px → 64px) |
| **Radius** | `--dsd-radius-{xs/sm/md/lg/xl/full}` |
| **Typography** | `--dsd-text-{xs–3xl}`, `--dsd-lh-{tight/normal/relaxed}`, `--dsd-fw-{regular–bold}` |
| **Elevation** | `--dsd-elev-{0–4}` |
| **Motion** | `--dsd-dur-{instant–crawl}`, `--dsd-ease-{out/in/inout/spring/linear}` |
| **Table** | `--dsd-table-row-h`, `--dsd-table-row-hover`, `--dsd-table-row-selected` |

Motion tokens collapse to `0ms` under `prefers-reduced-motion: reduce`.

---

## Components

### `StatusPill`
Colored badge with dot indicator for status/category variants.
```tsx
<StatusPill variant="success" label="Running" />
<StatusPill variant="agent" label="GPT-4o" size="md" />
```

### `DataTable<T>`
Typed sortable table with sticky header, dense mode, keyboard navigation, and virtualization-ready scroll container.
```tsx
<DataTable cols={cols} rows={data} rowKey={(r) => r.id} dense stickyHeader maxRows={15} />
```

### `SkeletonLine` / `SkeletonBlock` / `SkeletonTable` / `SkeletonCard`
Pulse-animated loading placeholders for lines, blocks, tables, and cards.
```tsx
<SkeletonTable rows={8} cols={5} />
<SkeletonLine width="60%" height={14} />
```

### `EmptyState`
Centered empty state with optional icon, description, and CTA.
```tsx
<EmptyState icon="🛸" title="No missions found" description="Create your first mission to get started." action={<DeckBtn>New Mission</DeckBtn>} />
```

### `ErrorState`
Alert-role error display with retry button; extracts `Error.message` automatically.
```tsx
<ErrorState error={err} onRetry={refetch} />
```

### `Toolbar`
Flex toolbar container with left/center/right slots.
```tsx
<Toolbar left={<DeckBtn>Export</DeckBtn>} right={<FilterCount n={3} />}>…chips…</Toolbar>
```

### `FilterBar`
Toggle-button filter strip with optional search input and counts.
```tsx
<FilterBar value={filter} onChange={setFilter} options={[{value:"all",label:"All",count:42}]} search={{value:q,onChange:setQ}} />
```

### `Drawer`
Slide-in side panel (left or right) with focus trap and Escape-to-close.
```tsx
<Drawer open={open} onClose={() => setOpen(false)} title="Trace Detail" width={480}>…</Drawer>
```

### `Timeline`
Vertical event list with status-colored dots and timestamps.
```tsx
<Timeline events={[{id:1, title:"Agent started", status:"success", timestamp:"12:04"}]} />
```

### `KeyValueGrid`
Responsive label/value definition list in 1–3 columns.
```tsx
<KeyValueGrid entries={[{key:"Model", value:"gpt-4o"}, {key:"Tokens", value:"1,234"}]} cols={2} />
```

### `Sparkline` / `MiniBar`
Pure SVG inline charts. No dependencies.
```tsx
<Sparkline data={[10,25,18,40,35]} width={80} height={28} />
<MiniBar data={[5,12,8,20]} color="var(--dsd-cat-cost)" />
```

---

## Accessibility

- All interactive elements have `focus-visible` outlines using `--dsd-border-focus`
- `role` and `aria-*` attributes set throughout (status, alert, grid, toolbar, dialog, img)
- Motion tokens collapse to `0ms` under `prefers-reduced-motion: reduce`
- `Drawer` traps focus and closes on Escape
- `DataTable` columns announce sort direction via `aria-sort`
