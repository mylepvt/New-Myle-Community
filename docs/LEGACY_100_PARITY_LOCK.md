# Legacy ↔ vl2 — parity lock (policy)

**Rule:** Purana **Flask Myle Dashboard** (legacy code under `backend/legacy/myle_dashboard_main3/`, plus original `database.py` / routes) **authority** hai—naya stack isi ko reproduce karta hai, guesswork nahi.

**“100% same” ka matlab engineering mein:** har shipped feature ke liye legacy behavior (roles, visibility, statuses, money, timezones) **match** ho, ya **`docs/LEGACY_PARITY_MAPPING.md`** mein **evidence + reason** ke saath likha ho ke kyun alag hai.

**Silent drift allowed nahi:** labels, rules, ya stub “done” mat rakho jab tak parity row update na ho.

**Technical pointers:** `docs/LEGACY_PARITY_MAPPING.md`, `docs/CORE_APP_STRUCTURE.md` (shell IA + journey lock), `docs/LOSSLESS_FULLSTACK_PORT.md`, `backend/legacy/LEGACY_TO_VL2_MAPPING.md`.

**Cursor:** `.cursor/rules/myle-legacy-100-parity-lock.mdc` (always on).
