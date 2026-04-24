# Local MongoDB (Docker)

Start the database in the background:

```bash
cd mongodb_docker
docker compose up -d
```

- **URL:** `mongodb://127.0.0.1:27017/giulia` (the app uses the database name `giulia` from the path).
- **Data:** a named volume `giulia_mongo_data` stores data across restarts.

Stop without removing the volume:

```bash
docker compose down
```

Stop and **delete** the volume (wipes the database):

```bash
docker compose down -v
```

**Collections (Giulia):**

| Collection  | Role |
|-------------|------|
| `chunks`    | Text chunks, provenance, numeric `faiss_id` after a rebuild, and a stored `embedding` (vector for FAISS and rebuilds) |
| `documents` | One row per **PDF path** and its `file_hash` and `last_processed` time for the incremental ingest |
