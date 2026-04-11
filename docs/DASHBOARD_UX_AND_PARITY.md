# Dashboard UX — purani app vs nayi app (guess‑free)

Yeh doc **product spec nahi** hai; yeh explain karti hai ke **abhi repo mein kya wired hai** aur parity **kaise close** hogi bina assumptions ke.

## Teen alag cheezein mat mix karo

1. **Legacy parity (product)** — purani app ka exact behavior sirf tab jab **`docs/LEGACY_PARITY_MAPPING.md`** mein **Evidence** ho. Wahan **nayi app ka factual inventory** bhi hai (kaunsa route `full` vs `stub`).
2. **`full` vs `stub` surface** — `frontend/src/config/dashboard-registry.ts` → `surface: 'full'` = real page component; **`stub`** = `ShellStubPage` → `GET` se chhota JSON (note/count). **Stub par “poora flow” nahi dikhega** — yeh bug nahi, scope hai.
3. **“Click kiya, kuch nahi hua” troubleshooting**
   - **Sidebar / Quick actions** = `NavLink` / `Link` — kaam karna chahiye agar session valid hai (`GET /auth/me` authenticated).
   - **Nested route** agar role allow na kare → **`Navigate` to `/dashboard`** (lagta hai click waste gaya).
   - **KPI cards / decorative tiles** jab tak **`Link`/`Button` se wrap** na hon — pehle **non-interactive** the (sirf numbers).
   - **Header search** — jab tak Leads par `?q=` wire na ho, **empty search** sirf navigate karta hai (ab wiring `DashboardLayout` + `LeadsWorkPage` se).

## “Gap” kaise band hoga (process)

| Step | Kaam |
|------|------|
| 1 | Purani app se **evidence** (screen, URL, rule) — `LEGACY_PARITY_MAPPING.md` matrix |
| 2 | Us row ke **new path** par `stub` hai to **API + UI** implement → `full` surface |
| 3 | **Roles** `dashboard-route-roles.json` + backend checks align |

Guess se nahi: matrix khali = **TBD**.

## Quick reference: kya abhi “real” hai (leads / work)

- **Leads, Workboard, Follow-ups (admin/leader), Pool, …** — `full` jahan registry kehta hai.
- **Execution, kai Other/Settings, kuch Finance** — abhi **`stub`** (placeholder API).
