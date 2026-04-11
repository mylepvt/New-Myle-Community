# Claude → Cursor Handoff — Myle vl2

**Last updated: 2026-04-11 (Session 3)** — meta dev-login gate, `create_user.py`, `POST /team/members` + Team UI; docs synced

---

## ✅ Ab kya kaam kar raha hai (fully working)

### Auto-Deploy Pipeline — END TO END ✅

```
git push origin main          (Mylecommunity/Myle-community)
        ↓
GitHub Actions: CI #14 ✅     (backend pytest + frontend lint/test/build)
        ↓
GitHub Actions: Sync ✅        (mirrors to mylepvt/New-Myle-Community)
        ↓
Render Auto-Deploy ✅          (watches mylepvt/New-Myle-Community main)
        ↓
https://new-myle-community.onrender.com  🚀 LIVE
```

**Render pe jo dikh raha hai:**
- "Deploy live for 64b6ac6" ✅ — 9:16 AM (latest)
- "New commit via Auto-Deploy" — matlab sync → render chain complete hai

---

## 🔧 Session 2 mein kya fix hua

### 1. Sync Workflow Fix — `github-actions[bot]` 403 Error

**Problem:** GitHub Actions ka credential helper `http.extraheader` inject karta hai
`Authorization: basic base64(x-access-token:GITHUB_TOKEN)` jo PAT ko override kar
deta tha. Git push fail hoti thi "denied to github-actions[bot]" se.

**Fix:** `.github/workflows/sync-to-mylepvt.yml` mein push se pehle header unset karo:

```yaml
- name: Push to mylepvt
  env:
    PAT: ${{ secrets.MYLEPVT_SYNC_PAT }}
    MYLEPVT_TARGET: mylepvt/New-Myle-Community
  run: |
    set -euo pipefail
    if [ -z "${PAT}" ]; then
      echo "::error::Add repository secret MYLEPVT_SYNC_PAT"
      exit 1
    fi
    # Remove GitHub Actions credential helper so PAT is used
    git config --unset-all http.https://github.com/.extraheader || true
    git remote add mylepvt "https://x-access-token:${PAT}@github.com/${MYLEPVT_TARGET}.git"
    git push mylepvt "HEAD:refs/heads/main"
```

**Secret setup (already done):**
- Repo: `Mylecommunity/Myle-community` → Settings → Secrets → Actions
- Secret name: `MYLEPVT_SYNC_PAT`
- Token: Classic PAT with `repo` + `workflow` scopes from `mylepvt` GitHub account
  (ya woh account jo `mylepvt/New-Myle-Community` mein push kar sakta hai)

---

### 2. CI Backend Fix — `No module named 'sqlalchemy'`

**Problem:** `pip install -r backend/requirements-dev.txt` root se run hota tha.
Andar ka `-r requirements.txt` relative to CWD (root) resolve hota tha, jahan
`requirements.txt` exist nahi karta. Isliye sqlalchemy, fastapi etc. install
nahi hote the (silently skip).

**Fix:** `--no-cache-dir` + `working-directory: backend` dono kaam nahi aaye.
Final fix = explicit `python -m pip install` with full package list:

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"

- name: Install Python dependencies
  run: |
    python -m pip install --upgrade pip
    python -m pip install \
      "fastapi>=0.115.0,<1.0.0" \
      "uvicorn[standard]>=0.32.0,<1.0.0" \
      "sqlalchemy[asyncio]>=2.0.36,<3.0.0" \
      "asyncpg>=0.29.0,<1.0.0" \
      "psycopg2-binary>=2.9.9,<3.0.0" \
      "alembic>=1.14.0,<2.0.0" \
      "pydantic-settings>=2.0.0,<3.0.0" \
      "PyJWT>=2.8.0,<3.0.0" \
      "aiosqlite>=0.20.0,<1.0.0" \
      "bcrypt>=4.1.0,<5.0.0" \
      "pytest>=8.0.0" \
      "httpx>=0.27.0" \
      "anyio[trio]"

- name: Pytest
  run: python -m pytest tests/ -q
```

**Why `python -m pip` instead of `pip`:** ensures exact same Python binary used
for both install and test.

---

## 📁 Repo Structure

| Remote | Repo | Purpose |
|--------|------|---------|
| `origin` | `Mylecommunity/Myle-community` | **Canonical** — sab commits yahan |
| (mirror) | `mylepvt/New-Myle-Community` | Render watches this (auto-synced via GH Actions) |

**Daily workflow:**
```bash
cd "/Users/karanveersingh/myle vl2"
# ... code changes ...
git add .
git commit -m "feat: ..."
git push origin main        # triggers CI → sync → Render auto-deploy
```

⚠️ **Worktree paths** (e.g. `.claude/worktrees/admiring-moore`) se confuse mat hona —
actual editing repo root mein hoti hai.

---

## 🔑 Key Files

| Area | Path |
|------|------|
| CI workflow | `.github/workflows/ci.yml` |
| Sync workflow | `.github/workflows/sync-to-mylepvt.yml` |
| Create user (CLI) | `backend/scripts/create_user.py` |
| Team admin create | `POST /api/v1/team/members` · `frontend/src/pages/TeamMembersPage.tsx` |
| WS endpoint | `backend/app/api/v1/realtime_ws.py` |
| WS hub/broadcast | `backend/app/core/realtime_hub.py` |
| Frontend WS hook | `frontend/src/hooks/use-realtime-invalidation.ts` |
| Hook mount | `frontend/src/components/layout/DashboardLayout.tsx` |
| App config | `backend/app/core/config.py` |
| API router | `backend/app/api/v1/router.py` |
| Dockerfile | `./Dockerfile` (monorepo root) |

---

## 🌐 Stack Summary

- **Backend:** FastAPI (async) + SQLAlchemy 2.0 + PostgreSQL (Render) / SQLite (tests)
- **Frontend:** React 19 + TypeScript + Vite + TailwindCSS + TanStack Query
- **Auth:** Cookie JWT (`myle_access` + `myle_refresh`)
- **Realtime:** WebSocket at `wss://<host>/api/v1/ws` (cookie auth, no user_id in URL)
- **Deploy:** Docker monorepo image — FastAPI serves React SPA from same origin

---

## 🔴 Render Environment Variables (production mein zaroori)

| Var | Value | Note |
|-----|-------|------|
| `DATABASE_URL` | Render internal Postgres URL | Already set |
| `SECRET_KEY` | 32+ random chars | `NEW_SECRET` alias bhi kaam karta hai |
| `AUTH_DEV_LOGIN_ENABLED` | `false` | Dev login disable karo production mein |
| `BACKEND_CORS_ORIGINS` | `https://new-myle-community.onrender.com` | Same-origin deploy |
| `PORT` | `10000` | Render default |

**Alembic migrations** (first deploy ya schema change ke baad):
```bash
# Render → Shell tab mein:
alembic upgrade head
```

---

## ✅ Verify Karna (next step)

1. **WebSocket live test:**
   - `https://new-myle-community.onrender.com` → login karo
   - Chrome DevTools → Network → WS filter
   - `api/v1/ws` entry → Status **101 Switching Protocols** ✅

2. **CI green check:**
   - `https://github.com/Mylecommunity/Myle-community/actions`
   - Latest run: CI ✅ + Sync ✅ dono green

---

## 🛣️ Roadmap — repo mein shipped vs tumhare account par

**Code / repo (done):**
- [x] Dev-login UI sirf jab **`GET /api/v1/meta` → `auth_dev_login_enabled`** true ho; prod copy mein dev password hint nahi
- [x] Real users: **`backend/scripts/create_user.py`** + **`POST /api/v1/team/members`** (admin) + **Team → All members → Add user**

**Host / ops (tum Render dashboard / Shell par):**
- [ ] **`SECRET_KEY`** (ya **`NEW_SECRET`**) — strong random; dev default mat chhodo
- [ ] **`AUTH_DEV_LOGIN_ENABLED=false`** production par confirm
- [ ] **`alembic upgrade head`** live DB (pehli deploy / migration ke baad)
- [ ] WebSocket **>1 instance** scale karte ho to **Redis pub/sub** (abhi `RealtimeHub` in-memory = single replica)

---

## 🐛 Known Gotchas

1. **`github-actions[bot]` 403 push error** → already fixed (extraheader unset)
2. **`No module named X` in CI** → already fixed (explicit `python -m pip install`)
3. **Render repo list mein `Mylecommunity` nahi dikh raha** → by design, `mylepvt` account se connected; sync workflow handle karta hai
4. **`.venv` local mein hai backend mein** → gitignored, CI pe affect nahi karta
5. **`cache: pip` in setup-python** → removed from CI; it was causing stale cache issues
