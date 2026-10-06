# Cara Menjalankan Pipeline

Panduan langkah demi langkah untuk menjalankan pipeline News RAG secara lokal.
Untuk penjelasan alur logikanya, lihat [alur-logic.md](alur-logic.md).

## 1. Prasyarat

- **Aktifkan conda environment:**

  ```bash
  conda activate paper-data
  ```

- **Pastikan dependency Python terinstall** (sekali saja, atau setelah
  `requirements.txt` berubah):

  ```bash
  pip install -r requirements.txt
  ```

- **Isi `OPENROUTER_API_KEY` di `.env`**. Semua pemanggilan LLM (generator,
  guardrail, dataset generator, judge) lewat OpenRouter, jadi tidak perlu
  container LLM.

- **Nyalakan container Docker** yang dibutuhkan (PostgreSQL, Qdrant):

  ```bash
  docker compose up -d postgres qdrant
  ```

  Cek semua container sudah sehat:

  ```bash
  docker compose ps
  ```

- **Siapkan file `.env`** dari contoh, lalu sesuaikan value-nya (kredensial
  Postgres, host/port Qdrant, dll):

  ```bash
  cp .env.example .env
  ```

- **Inisialisasi schema database** (dibuat otomatis juga saat
  `run_pipeline.py` dijalankan, tapi bisa dijalankan manual):

  ```bash
  python setup-db.py
  ```

## 2. Menjalankan seluruh pipeline sekaligus

```bash
python run_pipeline.py
```

Ini menjalankan berurutan: `scrape → clean → chunk → embed → pdf`, lalu
mencetak ringkasan (jumlah chunk yang diproses/diindeks, jumlah artikel yang
diekspor ke PDF).

## 3. Menjalankan tiap step secara terpisah

Gunakan flag `--step` untuk menjalankan satu tahap saja:

```bash
# 1. Scrape berita dari Google News RSS -> raw_articles
python run_pipeline.py --step scrape

# 2. Bersihkan & filter raw_articles -> clean_articles
python run_pipeline.py --step clean

# 3. Pecah clean_articles jadi chunk token-based
python run_pipeline.py --step chunk

# 4. Encode chunk (dense + sparse) & upsert ke Qdrant
python run_pipeline.py --step embed

# 5. Export clean_articles jadi PDF -> data/pdf/
python run_pipeline.py --step pdf
```

Opsi tambahan untuk step `pdf`:

```bash
# Override folder output PDF
python run_pipeline.py --step pdf --pdf-dir /path/lain

# Hanya export artikel yang dibuat sejak tanggal tertentu
python run_pipeline.py --step pdf --since-date 2026-08-01
```

## 4. Sinkronisasi hasil review dosen (`sync_reviewed.py`)

Setelah dosen selesai me-review PDF hasil step `pdf` (menambahkan kata
`"ok"` di nama file untuk yang disetujui) dan hasil review-nya sudah ada di
`data/classified-2/<language>/<topic_category>/[sub_area]/*.pdf`:

**Selalu jalankan `--dry-run` dulu** untuk melihat apa yang akan terjadi
tanpa benar-benar mengubah database:

```bash
python sync_reviewed.py --dry-run
```

Periksa ringkasannya (jumlah `deleted`, `kept`, `failed`). Kalau sudah sesuai
ekspektasi, baru jalankan tanpa `--dry-run` untuk benar-benar menghapus
artikel yang ditolak dari database:

```bash
python sync_reviewed.py
```

## 5. Menjalankan backend & frontend (opsional, untuk chatbot)

```bash
docker compose up -d backend frontend
```

- Backend (FastAPI) tersedia di `http://localhost:8686`.
- Frontend (Vite dev server, dijalankan langsung di dalam container) tersedia
  di `http://localhost:5888`.

Alternatif chatbot berbasis Streamlit (tanpa Docker):

```bash
streamlit run chatbot/app.py
```

## 6. Evaluasi kualitas chatbot (RAGAS + DeepEval)

Generate dataset Q&A emas dari artikel yang sudah ada (jalankan di dalam
Docker, butuh PostgreSQL + `OPENROUTER_API_KEY`). Model yang dipakai:
`DATASET_GENERATOR_MODEL`. Hasilnya ditulis ke
`evaluation/golden_dataset_openrouter.csv`:

```bash
docker compose run evaluation python evaluation/generate_dataset.py
```

Lalu skor chatbot terhadap dataset itu (selalu dari **luar** Docker, karena
memanggil backend lewat `http://localhost:8686`). Judge yang dipakai:
`JUDGE_MODEL`:

```bash
python -m evaluation.evaluate
```

Hasilnya ditulis ke `evaluation/results.csv`, dengan kolom `generator_model`
dan `judge_model` untuk setiap baris, plus ringkasan rata-rata tiap metrik
dicetak di terminal. Sebelum menjalankan ulang dengan dataset atau model baru,
hapus `evaluation/rag_outputs_checkpoint.json` dan `evaluation/checkpoint.json`
(lihat [evaluation.md](evaluation.md)). Detail lengkap: [evaluation.md](evaluation.md)
(Bahasa Inggris).

## 7. Menghapus artikel secara manual

Kalau ada artikel yang perlu dihapus (salah scrape, di luar topik, dsb.) dari
PostgreSQL **dan** Qdrant sekaligus, pakai `scripts/delete_articles_by_title.py`
daripada menghapus manual dari masing-masing database (berisiko salah satu
store jadi tidak sinkron):

```bash
python scripts/delete_articles_by_title.py "%myanmar%meth%"        # tampilkan match dulu, minta konfirmasi
python scripts/delete_articles_by_title.py "%myanmar%meth%" --yes  # langsung hapus tanpa konfirmasi
```

Lihat [scripts.md](scripts.md) (Bahasa Inggris) untuk script pemeliharaan
data lainnya.

## 8. Koneksi ke database (psql)

Connection string PostgreSQL mengikuti env var di `.env`
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`,
`POSTGRES_DB`). Contoh koneksi lewat `psql`, sesuai default di
`docker-compose.yml`/`.env`:

```bash
psql "postgresql://postgres-data-paper-child:secret-data-paper-child@127.0.0.1:5433/newsrag-data-paper-child"
```

Atau kalau env var `.env` sudah di-source ke shell:

```bash
psql "postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432}/$POSTGRES_DB"
```

Query cepat untuk cek jumlah data di tiap tabel:

```sql
SELECT count(*) FROM raw_articles;
SELECT count(*) FROM clean_articles;
SELECT count(*) FROM chunks;
```

Untuk cek isi Qdrant, gunakan health endpoint container Qdrant (default
port host `6335`, lihat `docker-compose.yml`):

```bash
curl http://localhost:6335/healthz
curl http://localhost:6335/collections
```
