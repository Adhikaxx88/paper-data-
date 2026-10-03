# Struktur File & Folder Proyek

Dokumen ini menjelaskan struktur folder dan file utama proyek `news-rag`.

## Tree Diagram

```
news-rag/
├── config.py                 # Semua konfigurasi (model, topik query, setting DB, dst.)
├── run_pipeline.py           # Entry point utama: menjalankan scrape→clean→chunk→embed→pdf
├── sync_reviewed.py          # Sinkronisasi hasil review dosen ke database
├── setup-db.py               # Inisialisasi schema database secara manual
├── requirements.txt          # Dependency Python
├── docker-compose.yml        # Orkestrasi container (postgres, qdrant, pipeline, backend, frontend)
├── Dockerfile.pipeline       # Image untuk menjalankan pipeline batch
├── Dockerfile.backend        # Image untuk menjalankan backend FastAPI
├── .env / .env.example       # Konfigurasi environment (kredensial, host, port, dll)
│
├── pipeline/                 # Script pipeline utama
│   ├── scraper.py            #   scrape Google News RSS -> raw_articles
│   ├── cleaner.py            #   filter & bersihkan raw_articles -> clean_articles
│   ├── chunker.py            #   pecah clean_articles jadi chunk token-based
│   ├── embedder.py           #   orkestrasi encode + upsert chunk ke Qdrant/Postgres
│   └── pdf_exporter.py       #   export clean_articles -> file PDF
│
├── vectorization/            # Logic encoding ke vector
│   ├── embedder.py           #   load model dense (multilingual-e5-large) & sparse (BM25)
│   └── qdrant_store.py       #   koneksi & operasi ke Qdrant (create collection, upsert, dsb.)
│
├── db/                       # Koneksi PostgreSQL dan schema
│   ├── postgres.py           #   koneksi, query helper, migrasi kolom
│   └── schema.sql            #   definisi seluruh tabel (raw_articles, clean_articles, chunks, dst.)
│
├── rag/                      # Retrieval-Augmented Generation logic
│   ├── retriever.py          #   ambil chunk relevan dari Qdrant (dense + sparse fusion)
│   ├── generator.py          #   panggil LLM (OpenRouter, RAG_GENERATOR_MODEL) untuk menyusun jawaban
│   └── pipeline.py           #   orkestrasi retrieve -> generate untuk satu pertanyaan
│
├── backend/                  # Backend FastAPI untuk chatbot (dipakai frontend React)
│   ├── main.py                #   /api/session, /api/history, /api/chat — dipakai frontend saat ini
│   ├── session.py             #   session store in-memory untuk /api/search (terpisah dari Postgres)
│   ├── routers/search.py      #   POST /api/search, GET /api/health — pipeline guardrail+rerank (belum dipakai frontend)
│   ├── guardrails/            #   input.py (6 check berurutan) & output.py (redact/truncate/allowlist), dipakai /api/search
│   ├── retrieval/searcher.py  #   hybrid_search() + rerank() (cross-encoder), dipakai /api/search
│   └── generation/generator.py #  generate_answer() versi /api/search (beda dari rag/generator.py)
│
├── chatbot/                  # Antarmuka chatbot alternatif berbasis Streamlit
│   └── app.py                #   panggil rag/pipeline.py langsung, tanpa lewat backend FastAPI
│
├── frontend/                 # Frontend React + Vite untuk antarmuka chat
│   └── src/
│       ├── App.tsx            #   layout utama, toggle dark mode, empty state
│       ├── api/chat.ts        #   panggilan ke /api/session & /api/chat
│       ├── hooks/useChat.ts   #   state pesan, session id (localStorage), sendMessage()
│       ├── components/        #   ChatInput.tsx, ChatMessage.tsx (dedup source per article_id, link sumber)
│       └── types/chat.ts      #   tipe ChatMessage untuk UI
│
├── evaluation/                # Evaluasi chatbot: golden dataset + skor RAGAS/DeepEval
│   ├── generate_dataset.py    #   generate Q&A Indonesia dari clean_articles via OpenRouter -> golden_dataset_openrouter.csv
│   ├── evaluate.py            #   jalankan golden_dataset_openrouter.csv lewat /api/chat, skor RAGAS + DeepEval (judge via OpenRouter) -> results.csv
│   └── .env.local             #   override host/port untuk run di luar Docker
│
├── scripts/                   # Script pemeliharaan data satu-kali / manual
│   └── delete_articles_by_title.py #  hapus artikel (Postgres + Qdrant) berdasarkan pola judul
│
├── data/                     # Data lokal (backup file, hasil olahan, folder review dosen)
│   ├── raw/                   #   backup lokal hasil scraping (data utama tetap di raw_articles)
│   ├── clean/                 #   backup lokal hasil cleaning (data utama tetap di clean_articles)
│   ├── clean-2/                #   folder backup cleaning tambahan/batch kedua
│   ├── chunks/                 #   hasil chunking teks artikel
│   ├── pdf/                    #   artikel clean dikonversi ke PDF, per language/topic_category/sub_area
│   ├── classified/              #   folder review dosen batch pertama (sudah diproses)
│   └── classified-2/            #   folder review dosen batch kedua (aktif dipakai sync_reviewed.py)
│
└── docs/                     # Dokumentasi proyek
    ├── alur-logic.md          #   penjelasan alur pipeline (Bahasa Indonesia)
    ├── cara-run.md            #   panduan menjalankan pipeline (Bahasa Indonesia)
    ├── struktur-file.md       #   dokumen ini
    ├── pipeline/README.md     #   penjelasan tiap file di pipeline/
    ├── vectorization/README.md #  penjelasan vectorization/embedder.py & qdrant_store.py
    ├── db/README.md           #   penjelasan schema.sql & postgres.py
    ├── data/README.md         #   penjelasan semua subfolder di data/
    ├── mkdocs.yml, index.md,  #   situs dokumentasi MkDocs (Bahasa Inggris) yang sudah ada
    ├── architecture.md,       #   sebelumnya — tidak diubah oleh dokumen ini
    ├── setup.md, frontend.md,
    ├── pipeline/*.md, database/*.md, rag/*.md
```

> **Catatan:** folder `docs/` sebelumnya sudah berisi situs dokumentasi
> MkDocs berbahasa Inggris (`docs/mkdocs.yml`, `docs/index.md`,
> `docs/architecture.md`, `docs/setup.md`, `docs/frontend.md`,
> `docs/pipeline/*.md`, `docs/database/*.md`, `docs/rag/*.md`). Dokumen
> Bahasa Indonesia di sini (`alur-logic.md`, `cara-run.md`,
> `struktur-file.md`, dan subfolder `pipeline/README.md`,
> `vectorization/README.md`, `db/README.md`, `data/README.md`) ditambahkan
> berdampingan, **tidak menggantikan** dokumentasi yang sudah ada.

## Penjelasan Folder Data

| Folder | Penjelasan |
|---|---|
| `data/raw/` | File lokal hasil scraping (backup). Data utama disimpan di PostgreSQL tabel `raw_articles`. |
| `data/clean/` | File lokal hasil cleaning (backup). Data utama disimpan di PostgreSQL tabel `clean_articles`. |
| `data/clean-2/` | Folder backup cleaning tambahan (belum ada file aktif saat dokumen ini ditulis). |
| `data/chunks/` | Hasil chunking teks artikel (potongan token ~500 dengan overlap 50 token). |
| `data/classified/` | Folder review dosen **batch pertama** — sudah diproses, tidak lagi dibaca oleh `sync_reviewed.py` (yang sekarang menunjuk ke `data/classified-2/`, lihat `sync_reviewed.py`). |
| `data/classified-2/` | Folder review dosen **batch kedua** — **aktif digunakan** oleh `sync_reviewed.py`. Terstruktur `<language>/<topic_category>/[sub_area]/*.pdf`, nama file mengandung kata `"ok"` untuk menandai artikel yang disetujui. |
| `data/pdf/` | Artikel `clean_articles` yang sudah dikonversi ke PDF oleh `pipeline/pdf_exporter.py`, terorganisir per `language/topic_category/sub_area`. Ini yang dikirim ke dosen untuk direview. |

## Penjelasan Folder Kode Utama

| Folder/File | Penjelasan |
|---|---|
| `pipeline/` | Semua script pipeline utama: `scraper.py` (scrape), `cleaner.py` (clean), `chunker.py` (chunk), `embedder.py` (orkestrasi embed), `pdf_exporter.py` (export PDF). Lihat [pipeline/README.md](pipeline/README.md). |
| `vectorization/` | Logic encoding teks ke vector: model dense `multilingual-e5-large` + sparse BM25 (`embedder.py`), dan operasi ke Qdrant (`qdrant_store.py`). Lihat [vectorization/README.md](vectorization/README.md). |
| `db/` | Koneksi PostgreSQL (`postgres.py`) dan definisi schema tabel (`schema.sql`). Lihat [db/README.md](db/README.md). |
| `backend/` | Backend **FastAPI** dengan **dua pipeline chat terpisah**: `main.py` (`/api/session`, `/api/history`, `/api/chat` lewat `rag/pipeline.py` — **ini yang dipakai frontend React sekarang**) dan `routers/search.py` + `guardrails/`, `retrieval/`, `generation/` (`/api/search`, `/api/health` — pipeline guardrail+hybrid search+rerank, belum dipakai UI mana pun tapi tetap berfungsi). Lihat [architecture.md](architecture.md#two-chat-backends-apichat-vs-apisearch) (Bahasa Inggris) untuk detailnya. |
| `chatbot/` | Antarmuka chat alternatif berbasis **Streamlit** (`chatbot/app.py`), memanggil `rag/pipeline.py` langsung tanpa lewat backend FastAPI. |
| `rag/` | Logic retrieval-augmented generation dipakai `backend/main.py`: `retriever.py` (ambil chunk relevan dari Qdrant, gabungan dense+sparse, tanpa rerank), `generator.py` (panggil LLM lewat OpenRouter), `pipeline.py` (orkestrasi retrieve→generate, simpan histori ke Postgres). |
| `config.py` | Semua konfigurasi terpusat: nama model embedding (`DENSE_MODEL_NAME`, `SPARSE_MODEL_NAME`), daftar topik/keyword pencarian (`TOPIC_QUERIES`, `TOPIC_QUERIES_ID`), setting chunking (`CHUNK_SIZE_TOKENS`, `CHUNK_OVERLAP_TOKENS`), setting koneksi database (`POSTGRES_URL`, `QDRANT_URL`), dan path folder data. |
| `sync_reviewed.py` | Script sinkronisasi hasil review dosen dari `data/classified-2/` ke database — hapus artikel yang ditolak, biarkan yang disetujui. |
| `scripts/` | Script pemeliharaan data manual/satu-kali di luar `run_pipeline.py`, mis. `delete_articles_by_title.py` untuk menghapus artikel (Postgres + Qdrant sekaligus) berdasarkan pola judul. Lihat [scripts.md](scripts.md). |
| `evaluation/` | Evaluasi kualitas chatbot: `generate_dataset.py` membuat dataset Q&A emas Bahasa Indonesia dari `clean_articles` via OpenRouter; `evaluate.py` menjalankan dataset itu lewat `/api/chat` dan menskornya dengan RAGAS (faithfulness, answer_relevancy, context_precision, context_recall) + DeepEval (hallucination). Lihat [evaluation.md](evaluation.md). |
| `run_pipeline.py` | Entry point CLI utama untuk menjalankan seluruh pipeline atau satu step tertentu (`--step scrape|clean|chunk|embed|pdf`). |
