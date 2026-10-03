# `vectorization/` — Encoding ke Vector

Folder ini berisi logic untuk mengubah teks menjadi vector (embedding) dan
menyimpannya ke Qdrant. Dipakai oleh `pipeline/embedder.py` saat proses
indexing, dan oleh `rag/retriever.py` saat proses pencarian (query).

## `embedder.py`

Memuat dan menjalankan dua model embedding secara native (pakai GPU kalau
tersedia, `cuda`, fallback ke `cpu`):

- **Dense model** — `intfloat/multilingual-e5-large` (`DENSE_MODEL_NAME` di
  `config.py`), dijalankan lewat `sentence-transformers`. Model e5 bersifat
  **asimetris**, artinya teks query dan teks passage/chunk harus diberi
  prefix yang berbeda sebelum di-encode:
  - `encode_passage(texts)` — dipakai saat **indexing** chunk. Menambahkan
    prefix `"passage: "` ke setiap teks sebelum encode.
  - `encode_query(query)` — dipakai saat **pencarian**. Menambahkan prefix
    dari `BGE_QUERY_INSTRUCTION` (`"query: "`) ke teks query sebelum
    encode.
  - Kedua fungsi menghasilkan vector yang sudah dinormalisasi
    (`normalize_embeddings=True`), cocok untuk cosine similarity.
- **Sparse model (BM25)** — `Qdrant/bm25` (`SPARSE_MODEL_NAME`), dijalankan
  lewat `fastembed`. Dipakai untuk pencarian berbasis keyword/leksikal.
  Fungsi: `encode_sparse(texts)`.

Kedua model dimuat sekali per proses (lazy singleton lewat
`get_dense_model()` / `get_sparse_model()`) dan dipakai ulang di semua
pemanggilan berikutnya, supaya tidak perlu load ulang model tiap kali
fungsi dipanggil.

## `qdrant_store.py`

Layer akses ke Qdrant untuk collection `news_chunks` (`QDRANT_COLLECTION`).
Setiap point (chunk) menyimpan **dua named vector**:

- `dense` — vector dense dari `embedder.py`, ukuran `EMBED_DIM` (1024,
  sesuai output `multilingual-e5-large`), jarak cosine.
- `bm25` — vector sparse BM25.

Kedua vector ini digabung saat pencarian lewat **RRF fusion** (dilakukan di
`rag/retriever.py`, bukan di file ini).

Fungsi-fungsi utama:

- `get_client()` — koneksi Qdrant, lazy singleton (pakai `QDRANT_URL` /
  `QDRANT_API_KEY` dari `config.py`).
- `init_collection()` — membuat collection `news_chunks` kalau belum ada.
- `recreate_collection()` — hapus lalu buat ulang collection dari nol.
  Dipanggil manual kalau ganti model embedding (dimensi vector berubah) —
  seluruh vector lama akan hilang dan harus di-embed ulang lewat
  `pipeline/embedder.py`.
- `point_exists(chunk_id)` — cek apakah chunk sudah pernah diindeks, dipakai
  supaya proses embed idempotent (tidak double-index).
- `upsert_chunks(chunks, dense_vecs, sparse_vecs)` — upsert batch chunk
  beserta vector dan payload-nya (termasuk `chunk_text` penuh dan metadata
  artikel) ke Qdrant, dalam batch berukuran 64 point.

> **Penting:** kalau `DENSE_MODEL_NAME` diganti ke model dengan dimensi
> output berbeda dari `EMBED_DIM` saat ini, collection Qdrant harus dibuat
> ulang lewat `recreate_collection()` sebelum embed ulang — kalau tidak,
> akan terjadi error mismatch dimensi vector.
