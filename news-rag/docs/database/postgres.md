# PostgreSQL

`db/postgres.py`, schema in `db/schema.sql`

PostgreSQL holds all structured, relational data: article metadata, full
chunk text, and chat history. See [Architecture](../architecture.md) for why
text lives here while vectors live in Qdrant.

## Full schema

```sql
CREATE TABLE articles (
    id UUID PRIMARY KEY,
    source TEXT,
    title TEXT,
    date DATE,
    url TEXT UNIQUE,
    category TEXT,
    drive_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chunks (
    chunk_id UUID PRIMARY KEY,
    article_id UUID REFERENCES articles(id),
    chunk_index INT,
    chunk_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chat_sessions (
    session_id UUID PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chat_messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES chat_sessions(session_id),
    role TEXT CHECK (role IN ('user', 'assistant')),
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Column descriptions

**`articles`**

| Column | Description |
|---|---|
| `id` | Deterministic UUID (`uuid5` of the article URL). |
| `source` | Publisher name (e.g. "Kompas.com"). |
| `title` | Article headline. |
| `date` | Publication date, normalized to ISO 8601 by the cleaner. |
| `url` | Canonical article URL. Unique — used for scrape-time deduplication. |
| `category` | The keyword this article was scraped under. |
| `drive_url` | Shareable link to the article's PDF backup on Google Drive, set by the PDF exporter. Null until then. |

**`chunks`**

| Column | Description |
|---|---|
| `chunk_id` | Deterministic UUID (`uuid5` of `article_id` + `chunk_index`). Also used as the Qdrant point id. |
| `article_id` | Foreign key to `articles.id`. |
| `chunk_index` | Position of this chunk within the article (0-based). |
| `chunk_text` | The chunk's raw text — the only place chunk text is stored. |

**`chat_sessions`** / **`chat_messages`**

| Column | Description |
|---|---|
| `session_id` | One row per chatbot conversation (a browser session, tracked client-side by the React frontend or Streamlit). |
| `role` | `user` or `assistant`. |
| `content` | The message text. |

## Key queries

**Fetch chunk text + article metadata by chunk_id (used by the retriever):**

```sql
SELECT c.chunk_id, c.chunk_text, a.title, a.source, a.date, a.category, a.url
FROM chunks c
JOIN articles a ON a.id = c.article_id
WHERE c.chunk_id = ANY(%s);
```

**Insert a chat message:**

```sql
INSERT INTO chat_messages (id, session_id, role, content)
VALUES (%s, %s, %s, %s);
```

**Fetch the last N messages of a session (used to build conversation history):**

```sql
SELECT role, content, created_at
FROM chat_messages
WHERE session_id = %s
ORDER BY created_at DESC
LIMIT %s;
```

All of these are wrapped by typed functions in `db/postgres.py`
(`get_chunks_by_ids`, `insert_message`, `get_recent_messages`, etc.) — no raw
SQL is written outside that module.
