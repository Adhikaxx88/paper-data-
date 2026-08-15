# Frontend

`frontend/` — a React + TypeScript chatbot UI that talks to the
[FastAPI backend](rag/pipeline.md) over HTTP. It replaces the Streamlit
prototype (`chatbot/app.py`, still available for quick local testing without
a frontend build — see [Setup](setup.md#run-the-chatbot)) as the primary UI.

## Component tree

```
App
├── (useSession, useChat hooks)
├── ChatWindow
│   ├── MessageBubble  (one per message)
│   │   └── SourceCard  (one per retrieved source, assistant messages only)
│   └── LoadingDots  (shown while awaiting a response)
└── InputBar
```

- **`App.tsx`** — top-level layout: fixed header, scrollable `ChatWindow`,
  fixed-bottom `InputBar`. Wires `useSession` and `useChat` together.
- **`ChatWindow.tsx`** — renders the message list, auto-scrolls to the
  newest message, and shows an empty-state prompt before the first message.
- **`MessageBubble.tsx`** — one chat bubble; right-aligned/blue for the
  user, left-aligned/white for the assistant. Assistant content is rendered
  as Markdown (`react-markdown`) so citations and lists format correctly.
- **`SourceCard.tsx`** — a collapsed-by-default card under each assistant
  message showing one retrieved source article.
- **`InputBar.tsx`** — the message composer: an auto-resizing textarea
  (Enter to send, Shift+Enter for a newline) and a send button.
- **`LoadingDots.tsx`** — a three-dot typing indicator shown while the
  backend is generating a response.

## Session persistence: localStorage → FastAPI → PostgreSQL

1. On first load, `useSession` checks `localStorage` for a `rag_session_id`.
2. If missing, it calls `POST /api/session`, which inserts a row into
   PostgreSQL's `chat_sessions` table and returns a new `session_id`. That id
   is cached in `localStorage`.
3. `useChat` loads any existing history for that session via
   `GET /api/history/{session_id}` on mount, so reloading the page in the
   same browser restores the conversation.
4. Every message sent via `POST /api/chat` is persisted server-side to
   `chat_messages` by `rag/pipeline.py` — the frontend does not store
   message content itself beyond the current page's in-memory React state.

Opening the app in a different browser (or after clearing `localStorage`)
starts a new session with no history, but the old session's messages remain
queryable in PostgreSQL by their `session_id`.

## Sources display: how score is shown

Each assistant message carries a `sources` array (`title`, `source`, `date`,
`score`) returned by `POST /api/chat`. `SourceCard` renders the source's
title as a collapsed header; expanding it reveals the publisher, date, and a
horizontal relevance bar whose fill width is `score * 100%` (Qdrant's cosine
similarity, 0–1) — a quick visual read on how strongly that article matched
the question, without needing to read the raw float.

## Dev mode

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173` by default. `vite.config.ts` proxies
`/api/*` requests to `http://localhost:8000`, so run the FastAPI backend
separately (`uvicorn backend.main:app --reload`, or the full local stack —
see [Setup](setup.md#running-with-local-stack-docker)) alongside `npm run dev`.

## Production

The `frontend` service in `docker-compose.yml` builds a static production
bundle (`npm run build`) and serves it via nginx (`frontend/nginx.conf`),
which also proxies `/api/` to the `backend` container. Once
`docker compose up backend frontend` is running, the chatbot is available at
`http://localhost:3000`.
