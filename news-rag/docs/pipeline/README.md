# `pipeline/` — Script Pipeline Utama

Folder ini berisi lima script yang membentuk pipeline batch News RAG, dari
scraping sampai export PDF. Setiap script punya satu tanggung jawab dan
dipanggil berurutan oleh `run_pipeline.py` (lihat
[../cara-run.md](../cara-run.md) dan [../alur-logic.md](../alur-logic.md)
untuk penjelasan alur & cara menjalankannya).

> Untuk penjelasan versi Bahasa Inggris yang lebih detail per file, lihat
> juga `docs/pipeline/*.md` (situs MkDocs yang sudah ada sebelumnya).

## `scraper.py`

Scrape Google News lewat RSS untuk daftar keyword/topik di `config.py`
(`TOPIC_QUERIES` untuk Bahasa Inggris, `TOPIC_QUERIES_ID` untuk Bahasa
Indonesia). Link Google News di-decode ke URL asli, isi artikel diambil
dengan `trafilatura`, lalu disimpan langsung ke tabel `raw_articles` di
PostgreSQL. Fungsi utama: `fetch_and_store()`.

## `cleaner.py`

Membaca baris `raw_articles` yang belum dibersihkan, menormalisasi teksnya
(hapus HTML/karakter aneh/whitespace berlebih), lalu memfilter: harus punya
konten, panjang minimum (`MIN_CONTENT_LENGTH`), menyebut kata "indonesia",
dan belum ada duplikatnya di `clean_articles` (dicek berdasarkan URL). Hasil
yang lolos disimpan ke tabel `clean_articles`. Fungsi utama:
`clean_and_store()`.

## `chunker.py`

Memecah teks tiap `clean_articles` menjadi potongan (chunk) ~500 token
dengan overlap 50 token, memakai tokenizer `tiktoken`. Setiap chunk diberi
id deterministik (`uuid5` dari URL + index chunk) supaya proses embed
idempotent. Fungsi utama: `chunk_articles()`.

## `embedder.py`

Mengorkestrasi proses embedding: memanggil `vectorization/embedder.py`
untuk encode teks chunk (dense `multilingual-e5-large` + sparse BM25), lalu
memanggil `vectorization/qdrant_store.py` untuk upsert vector+payload ke
Qdrant. Teks chunk juga disimpan ke tabel `chunks` di PostgreSQL. Fungsi
utama: `embed_and_store(chunks)`.

## `pdf_exporter.py`

Mengambil `clean_articles` yang belum pernah diekspor (`drive_url` masih
kosong), lalu merender tiap artikel jadi file PDF (`fpdf`) di
`data/pdf/<language>/<topic_category>/<sub_area>/<judul-slug>-<id8>.pdf`.
File-file inilah yang dikirim ke dosen untuk direview, sebelum hasilnya
disinkronkan kembali lewat `sync_reviewed.py` (di root proyek, bukan bagian
dari `pipeline/`).
