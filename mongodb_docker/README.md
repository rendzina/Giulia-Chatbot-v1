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
| `chunks`    | Text chunks, provenance, numeric `faiss_id`, and stored embeddings used for FAISS rebuilds |
| `documents` | One row per indexed source path (`.pdf`, `.docx`, `.txt`) with `file_hash` and `last_processed` |
