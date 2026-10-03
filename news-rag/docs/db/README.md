# `db/` — Koneksi PostgreSQL & Schema

Folder ini berisi seluruh akses ke PostgreSQL: definisi schema tabel dan
layer koneksi/query yang dipakai oleh semua script pipeline.

## `schema.sql`

Definisi seluruh tabel yang dipakai proyek ini:

| Tabel | Diisi oleh | Keterangan |
|---|---|---|
| `raw_articles` | `pipeline/scraper.py` | Artikel mentah hasil scraping. `url` bersifat unik (mencegah duplikat scrape). |
| `clean_articles` | `pipeline/cleaner.py` | Artikel yang sudah lolos filter cleaning, satu baris per `raw_articles` (relasi lewat `raw_id`, unik). Baris `raw_articles` tanpa pasangan di `clean_articles` dianggap "belum dibersihkan". |
| `chunks` | `pipeline/embedder.py` | Potongan teks artikel (chunk) beserta `article_id` yang merujuk ke `clean_articles`. |
| `chat_sessions` | `backend/main.py` / `chatbot/app.py` | Sesi percakapan chatbot. |
| `chat_messages` | `backend/main.py` / `chatbot/app.py` | Pesan per sesi (`role`: `user` atau `assistant`). |
| `articles` | (legacy) | Tabel lama, dipertahankan untuk kompatibilitas; alur pipeline saat ini memakai `raw_articles`/`clean_articles`. |

Index dibuat untuk kolom yang sering dipakai untuk filter/join:
`article_id` di `chunks`, `session_id` di `chat_messages`, serta
`topic_category`, `sub_area`, `keyword`, dan `drive_url IS NULL` (untuk
mempercepat query "artikel yang belum diekspor ke PDF") di
`raw_articles`/`clean_articles`.

Jalankan manual lewat `psql` kalau perlu:

```bash
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432}/$POSTGRES_DB" -f db/schema.sql
```

Semua `CREATE TABLE`/`CREATE INDEX` memakai `IF NOT EXISTS`, jadi aman
dijalankan berulang kali.

## `postgres.py`

Layer akses PostgreSQL yang dipakai seluruh pipeline. Bagian pentingnya:

- **Koneksi:**
  - `get_connection()` — buka koneksi baru, **caller yang bertanggung
    jawab** commit & close (dipakai script yang melakukan banyak operasi
    dalam satu koneksi, seperti `scraper.py`, `cleaner.py`,
    `pdf_exporter.py`).
  - `_connection_scope()` — context manager internal yang auto-commit saat
    sukses dan auto-rollback saat error, lalu selalu menutup koneksi.
- **Schema & migrasi:**
  - `init_schema()` — menjalankan `schema.sql` (idempotent, dipanggil
    otomatis oleh `run_pipeline.py` setiap run).
  - Fungsi migrasi tambahan (`migrate_add_sub_area`,
    `migrate_add_keyword_fields`, `migrate_add_language_field`, dst.) untuk
    menambah kolom baru ke tabel lama tanpa perlu drop/recreate.
- **Query helper** yang dipakai tiap tahap pipeline, misalnya
  `insert_raw_article`, `get_uncleaned_raw_articles`, `url_exists_in_clean`,
  `insert_clean_article`, `get_all_clean_articles`,
  `get_articles_without_drive_url`.

Semua fungsi di sini memakai `POSTGRES_URL` dari `config.py`, yang
disusun dari env var `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`,
`POSTGRES_PORT`, `POSTGRES_DB` (lihat `.env`).
