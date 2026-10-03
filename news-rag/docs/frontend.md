# Frontend

`frontend/` — a React + TypeScript chat UI (`src/App.tsx`) that talks to
`POST /api/session` and `POST /api/chat` (see
[api.md#post-apichat](api.md#post-apichat)) over HTTP. It replaces the
Streamlit prototype (`chatbot/app.py`, still available for quick local
testing — that one calls `rag/pipeline.py` directly, without going through
the FastAPI backend at all).

> The backend also exposes a separate, more elaborate `POST /api/search`
> pipeline (guardrails + reranking — see
> [architecture.md#two-chat-backends-apichat-vs-apisearch](architecture.md#two-chat-backends-apichat-vs-apisearch)).
> The frontend does **not** call it; everything below is about the
> `/api/chat` integration the UI actually uses.

## Component tree

```
App
├── (useChat hook)
├── ChatMessage  (one per turn — user or assistant)
└── ChatInput
```

- **`App.tsx`** — top-level layout: `h-screen flex flex-col` with a header
  (title + dark-mode toggle), a scrollable message list that centers an
  empty-state prompt when there are no messages yet, and a
  `ChatInput` pinned to the bottom. Wires `useChat` together with the
  message list and auto-scroll (`messagesEndRef.scrollIntoView`).
- **`hooks/useChat.ts`** — owns `messages`, `loading`, `sessionId`, and
  `sendMessage(query)`. See [Session persistence](#session-persistence) and
  [Message flow](#message-flow) below.
- **`api/chat.ts`** — thin fetch wrappers: `createSession()` (`POST
  /api/session`) and `sendChatMessage(sessionId, message)` (`POST
  /api/chat`), plus the `SourceItem`/`ChatResponse` types mirroring the
  backend's `SourceOut`/`ChatResponse` Pydantic models. Reads the API base
  URL from `VITE_API_URL`, defaulting to `http://localhost:8000`.
- **`types/chat.ts`** — the `ChatMessage` UI type (`id`, `role`, `content`,
  `timestamp`, optional `sources`/`error`), distinct from the API's
  `ChatResponse`/`SourceItem` types in `api/chat.ts`.
- **`components/ChatInput.tsx`** — the message composer: an auto-resizing
  textarea (grows up to 5 rows via a `useEffect` measuring `scrollHeight`,
  then scrolls), a 500-char `maxLength`, Enter to send / Shift+Enter for a
  newline, and a `→` send button disabled while empty or `loading`.
- **`components/ChatMessage.tsx`** — renders one turn:
  - a **user** message is a right-aligned bubble (`ml-auto`, `max-w-[80%]`,
    `var(--bubble-bg)` background);
  - an **error** turn (network/HTTP failure — see [Message flow](#message-flow))
    renders just the error text in red;
  - an **assistant** message is a left-bordered block (`var(--accent-bar)`)
    with an "Assistant" label, the answer text, and — if any sources came
    back — a `Show sources (N)` / `Hide sources` toggle. Expanding it lists
    each source's title (a clickable link when `url` is set, opening in a
    new tab; plain text otherwise) and a `source · date` byline.

  **Source deduplication:** multiple retrieved chunks can come from the
  same article. Before rendering, `ChatMessage` filters `sources` down to
  one card per distinct `article_id` (keeping the first — i.e.
  highest-ranked — chunk for each), via a `Set<string>` of seen ids. A
  source with no `article_id` is always kept rather than risk dropping a
  distinct source that happens to hash to the same falsy value.

## Session persistence

`useChat.ts` reads/writes `localStorage["rag_session_id"]` directly:

1. On first render, `sessionId` state initializes from
   `localStorage.getItem("rag_session_id")` (or `""` if unset/unavailable).
2. `sendMessage()` only calls `createSession()` (`POST /api/session`) when
   `sessionId` is still empty — `/api/chat` requires a valid session UUID,
   unlike `/api/search`'s "pass `\"\"` to start fresh" convention.
3. Once a session id is obtained (stored or freshly created), it's reused
   for every subsequent `sendChatMessage()` call and written to
   `localStorage` so it survives a reload.

`localStorage` reads/writes are wrapped in `try/catch` so a private-mode
browser or disabled storage degrades to a fresh session each send instead
of throwing.

## Message flow

`sendMessage(query)`:
1. Immediately appends a `user` message to `messages` and sets `loading`.
2. Ensures a `sessionId` exists (creating one via `POST /api/session` if
   not — see above).
3. Calls `sendChatMessage(sessionId, query)` (`POST /api/chat`).
4. On success, appends an `assistant` message carrying `content` (the
   `answer`) and `sources` (the `SourceItem[]` array, deduplicated and
   rendered by `ChatMessage` as described above).
5. On any error (network failure or non-2xx response), appends an
   `assistant` message with an `error` field instead of `content`,
   `ChatMessage` then rendering just that error text.
6. Clears `loading` in a `finally`.

## Empty state

Before the first message, the message area centers a prompt — "Tanyakan
sesuatu tentang kesehatan mental remaja Indonesia" — under a "Research
Database" eyebrow label, plus 3 example question chips (2 Indonesian, 1
English, mirroring the app's bilingual scope). Clicking a chip calls
`sendMessage()` with that question directly — same code path as typing and
submitting.

## Theming: light mode by default, dark toggle

The UI defaults to a **light** theme and switches to dark only if
`prefers-color-scheme: dark` matches on first load (`App.tsx`'s `dark`
state initializer). A `🌙`/`☀` button in the header flips that `dark`
boolean, toggling the `dark` class on `document.documentElement`. The
toggle is UI-only state — it is not persisted across reloads (unlike
session id).

Colors themselves are CSS custom properties defined on `:root` in
`src/index.css` (`--bg-page`, `--bg-content`, `--border`, `--bubble-bg`,
`--accent-bar`, etc.), each overridden inside a `.dark { ... }` block. This
is separate from Tailwind's own `dark:` utility classes (still used
directly on some elements, e.g. `dark:text-neutral-100`), which are enabled
for class-based toggling via `@custom-variant dark (&:where(.dark, .dark
*));` in the same file — both mechanisms key off the same `dark` class on
`<html>`.

## Dev mode

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`. `vite.config.ts` proxies `/api/*` to
`http://localhost:8000`, so run the FastAPI backend separately alongside
`npm run dev` — see [quickstart.md](quickstart.md).

## Production / Docker

The `frontend` service in `docker-compose.yml` currently runs the Vite dev
server itself inside the container (`node:20-slim` image, `npm install &&
npm run dev -- --host 0.0.0.0`), publishing port `5173` — **not** the
built static bundle. `frontend/Dockerfile` (multi-stage build → nginx,
`frontend/nginx.conf` proxying `/api/` to `backend:8000`) still exists and
works if built/run directly, but `docker-compose.yml` does not currently
reference it. `docker compose up backend frontend` therefore serves the
same dev-mode UI as running `npm run dev` locally, at
`http://localhost:5173`.
