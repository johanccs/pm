# Frontend — Kanban Studio

## Overview

A frontend-only Kanban board demo. Built with Next.js 16 (App Router), React 19, Tailwind CSS 4, and @dnd-kit for drag-and-drop. All state is in-memory; there is no backend integration, authentication, or persistence yet.

## Stack

- **Framework:** Next.js 16, App Router
- **Language:** TypeScript
- **Styling:** Tailwind CSS 4 (`@import "tailwindcss"` in globals.css), PostCSS
- **Drag-and-drop:** @dnd-kit/core, @dnd-kit/sortable, @dnd-kit/utilities
- **Fonts:** Space Grotesk (display), Manrope (body) — loaded via `next/font/google`
- **Testing:** Vitest + Testing Library (unit), Playwright (e2e)

## Directory Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx        # Root layout; loads fonts, imports globals.css
│   │   ├── page.tsx          # Root page; renders <KanbanBoard />
│   │   └── globals.css       # Tailwind import + CSS variables for color scheme
│   ├── components/
│   │   ├── KanbanBoard.tsx       # Client root component; owns all board state
│   │   ├── KanbanBoard.test.tsx  # Vitest + Testing Library tests for the board
│   │   ├── KanbanColumn.tsx      # Droppable column with editable title
│   │   ├── KanbanCard.tsx        # Sortable card with remove button
│   │   ├── KanbanCardPreview.tsx # Read-only card used in drag overlay
│   │   └── NewCardForm.tsx       # Collapsible add-card form
│   ├── lib/
│   │   ├── kanban.ts         # Types, seed data, and pure board logic helpers
│   │   └── kanban.test.ts    # Vitest unit tests for helpers
│   └── test/
│       ├── setup.ts          # Vitest global setup (jest-dom matchers)
│       └── vitest.d.ts       # Type augmentations for vitest
└── tests/
    └── kanban.spec.ts        # Playwright e2e tests (runs against npm run dev)
```

## Data Model (`src/lib/kanban.ts`)

```ts
type Card = { id: string; title: string; details: string }
type Column = { id: string; title: string; cardIds: string[] }
type BoardData = { columns: Column[]; cards: Record<string, Card> }
```

Seed data (`initialData`): 5 columns, 8 hardcoded cards.

Pure helpers:
- `moveCard(columns, activeId, overId)` — handles same-column reorder, cross-column move, and drop-on-column vs drop-on-card
- `createId(prefix)` — generates IDs for new cards
- `findColumnId` / `isColumnId` — internal helpers

## Component Roles

| Component | Role |
|-----------|------|
| `KanbanBoard` | `"use client"` root. Holds `board: BoardData` and `activeCardId` in `useState`. Manages `DndContext` + `DragOverlay`, column rename, add card, delete card, and drag-end handlers. |
| `KanbanColumn` | `useDroppable` droppable zone. Editable column title (inline input). `SortableContext` containing cards in vertical list order. Embeds `NewCardForm`. |
| `KanbanCard` | `useSortable` sortable item. Displays title + details. Remove button calls `onDelete`. |
| `KanbanCardPreview` | Read-only card chrome rendered inside `DragOverlay` while dragging. |
| `NewCardForm` | Collapsed by default. Expands to a form with required title + optional details field. Calls `onAdd` and resets on submit. |

## Drag-and-Drop

- Sensor: `PointerSensor` with 6px activation distance
- Collision detection: `closestCorners`
- Drop targets: columns (via `useDroppable`) and cards (via `useSortable`)
- Overlay: `KanbanCardPreview` shown during active drag

## Color Scheme (CSS variables in `globals.css`)

| Variable | Value | Usage |
|----------|-------|-------|
| `--accent-yellow` | `#ecad0a` | Accent lines, highlights |
| `--primary-blue` | `#209dd7` | Links, key sections |
| `--secondary-purple` | `#753991` | Submit buttons, important actions |
| `--dark-navy` | `#032147` | Main headings |
| `--gray-text` | `#888888` | Supporting text, labels |

## Testing

**Unit (Vitest + Testing Library)**
```
npm run test:unit        # run once
npm run test:unit:watch  # watch mode
```
- `src/lib/kanban.test.ts` — tests for `moveCard` and `createId`
- `src/components/KanbanBoard.test.tsx` — render and interaction tests

**E2E (Playwright)**
```
npm run test:e2e
```
- `tests/kanban.spec.ts` — runs against `npm run dev` on `127.0.0.1:3000`

**All tests**
```
npm run test:all
```

## What Is NOT Yet Present

- Authentication / login page
- Any API calls or data fetching (no `fetch`, no HTTP client)
- Backend integration
- AI sidebar
- Persistence (board resets on page reload)
- The `output: "export"` config needed for static build serving (added in Part 3)
