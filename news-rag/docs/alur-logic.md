Oke, hapus dari dua tempat: PostgreSQL + Qdrant.

Step 1 — Cari ID-nya dulu di PostgreSQL:

bash
docker exec -it <backend_container> psql -U postgres -d <dbname> -c `
  "SELECT id, title, source FROM clean_articles WHERE title ILIKE '%myanmar%meth%' OR title ILIKE '%meth bust%';"

Step 2 — Delete dari PostgreSQL:

bash
docker exec -it <backend_container> psql -U postgres -d <dbname> -c `
  "DELETE FROM clean_articles WHERE title ILIKE '%myanmar%meth%';"

(kalau ada raw_articles juga):

bash
docker exec -it <backend_container> psql -U postgres -d <dbname> -c `
  "DELETE FROM raw_articles WHERE title ILIKE '%myanmar%meth%';"

Step 3 — Delete chunk-nya dari Qdrant:

bash
docker exec -it <backend_container> python3 -c "
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchText

client = QdrantClient(host='qdrant', port=6333)
client.delete(
    collection_name='articles',
    points_selector=Filter(
        must=[FieldCondition(key='title', match=MatchText(text='myanmar'))]
    )
)
print('Done')
"

Ganti articles sama nama collection Qdrant kamu. Mau gw buatin script .py-nya sekalian biar tinggal run?