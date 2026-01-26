# Scalability Analysis & Refactoring Report

**Goal**: Prepare `frontend` for 10x user growth in 6 months.
**Current Status**: Prototype/MVP stage.
**Risk Level**: 🔴 High. The current architecture will likely fail under load (1000+ items).

## 1. Critical Performance Bottlenecks (Must Fix)

### 🛑 No Pagination (The "White Screen" Risk)
**Location**: `src/lib/apis.ts`, `Leads.jsx`, `Inbox.jsx`
- **Issue**: The application fetches *all* data (leads, conversations, templates) on load.
- **Impact**:
    - With 100 leads: Fast.
    - With 10,000 leads: app startup takes 10+ seconds, browser memory spikes, UI creates 10,000 DOM nodes.
    - **Leads.jsx**: Client-side filtering (`filteredLeads`) becomes slow on every keystroke.
- **Recommendation**: Implement server-side pagination for `getLeads` and `getConversations`.

### 🛑 "God Object" State & Blocking Startup
**Location**: `src/context/AppContext.jsx`
- **Issue**: `fetchInitialData` uses `Promise.all` to fetch *everything* before the app is "ready".
- **Impact**:
    - As data grows, the "Loading..." spinner will persist for longer and longer.
    - One failed API call (e.g., generic `getAnalytics`) can block the entire dashboard from loading.
    - Updates to `conversations` (via WebSocket) trigger re-renders for the entire app tree consuming context.
- **Recommendation**:
    - Adopt **TanStack Query (React Query)** for data fetching. It handles caching, background updates, and loading states granularly.
    - Remove data (templates, leads, stats) from `AppContext`. Keep `AppContext` for global auth/theme only.

### 🛑 Hardcoded Configuration
**Location**: `src/lib/apis.ts`
- **Issue**: `const API_BASE_URL = 'http://localhost:8000';`
- **Impact**: Cannot deploy to production/staging without code changes.
- **Recommendation**: Use `import.meta.env.VITE_API_BASE_URL`.

## 2. Rendering & UX Issues

### ⚠️ Lack of List Virtualization
**Location**: `Leads.jsx` (Table), `Inbox.jsx` (Chat List)
- **Issue**: Rendering complete DOM lists for large datasets.
- **Impact**: Scroll lag and frozen UI when lists exceed ~200 items.
- **Recommendation**: Use `react-virtuoso` or `react-window` to render only visible items.

### ⚠️ WebSocket Efficiency
**Location**: `AppContext.jsx`, `Inbox.jsx`
- **Issue**: WebSocket updates trigger full array mapping `prev.map(...)`.
- **Impact**: If 50 events arrive per second (implied by 10x scale "human attention" or bot activity), the main thread will be blocked by array operations.
- **Recommendation**: React Query's `setQueryData` is more optimized for this, or use a `Map` structure instead of Array for O(1) lookups.

## 3. Tech Debt & Quality

### ⚠️ Missing Error Boundaries
- **Issue**: No `ErrorBoundary` in `Layout.jsx` or `App.jsx`.
- **Impact**: A crash in `ChatViewer` (e.g., malformed message) crashes the whole app (white screen).
- **Recommendation**: Wrap top-level routes and widgets in Error Boundaries.

### ⚠️ Raw Fetch API
- **Issue**: `src/lib/apis.ts` manually handles tokens and errors.
- **Impact**: Boilerplate. Hard to implement features like "auto-retry on 500" or "refresh token on 401".
- **Recommendation**: Switch to a robust fetcher (axios or mande) or keep `fetch` but wrap it with React Query for the "management" aspect.

---

## 4. Proposed Refactoring Plan (Ranked by ROI)

| Phase | Task | Impact | Effort |
| :--- | :--- | :--- | :--- |
| **1 (Critical)** | **Externalize Env Vars** (`API_BASE_URL`) | Prod Ready | Low |
| **2 (Critical)** | **Integrated React Query** | Perf/Cache | Med |
| **3 (Critical)** | **Implement Pagination** (Leads, Inbox) | Scalability | Med |
| **4 (High)** | **Virtualize Lists** (Leads Table) | UX Perf | Med |
| **5 (Med)** | **Add Error Boundaries** | Stability | Low |

### Immediate "Low Hanging Fruit" Code Change
I recommend starting with **Phase 1 & 2**: Install `tanstack/react-query`, configure the API client to use Environment Variables, and refactor `Leads.jsx` to use a query instead of `useEffect`.
