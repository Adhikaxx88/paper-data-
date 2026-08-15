# Chunker

`pipeline/chunker.py`

## Chunking strategy

Article `content` is tokenized with `tiktoken` (`cl100k_base` encoding) and
split into overlapping windows:

- **Chunk size:** 500 tokens (`CHUNK_SIZE_TOKENS`)
- **Overlap:** 50 tokens (`CHUNK_OVERLAP_TOKENS`)

Each window advances by `chunk_size - overlap` (450) tokens, so consecutive
chunks share their last 50 tokens with the next chunk's first 50 tokens.

### Why these values

- **500 tokens** keeps each chunk small enough to be a focused, specific unit
  of context for retrieval (a chunk should be about one sub-topic of an
  article, not the whole thing), while staying well within GPT-4o-mini's
  context window even when several chunks are retrieved together.
- **50-token overlap** (10% of chunk size) prevents a sentence or idea that
  straddles a chunk boundary from being cut in a way that loses meaning in
  both halves, at a modest storage/embedding cost.

## Deterministic IDs

`article_id` and `chunk_id` are derived deterministically:

- `article_id = uuid5(NAMESPACE_URL, url)`
- `chunk_id = uuid5(article_id, str(chunk_index))`

This means re-chunking the same article always produces the same ids, which
is what makes the [embedder](embedder.md)'s "skip already-indexed chunks"
check work without needing a database round-trip during chunking itself.

## Example: one article → N chunks

An article with 1,200 tokens of content produces:

- Chunk 0: tokens `[0:500]`
- Chunk 1: tokens `[450:950]`
- Chunk 2: tokens `[900:1200]` (final, shorter chunk)

Each chunk record carries: `chunk_id`, `article_id`, `source`, `title`,
`date`, `category`, `url`, `chunk_index`, `chunk_text`.

## Output

- `data/chunks/chunks_<timestamp>.json`
