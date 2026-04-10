# Config templates

| File | Purpose |
|------|---------|
| `.env.production.example` | Variables for `docker-compose.prod.yml` — copy to repo root as `.env.production` (gitignored). |
| `../backend/.env.example` | Local backend dev (`docker compose` dev stack uses compose env, not always this file). |
| `../render.yaml` | Optional **Render** Blueprint (Postgres + Docker API + static frontend) — see header comments for `VITE_API_URL` / CORS order. |

**Dev stack:** root `docker-compose.yml`.  
**Prod reference:** root `docker-compose.prod.yml` + `.env.production`.
