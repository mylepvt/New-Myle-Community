# Existing team — smooth shift (old app → Myle vl2)

Goal: Jinhone **purani app** use ki hai, unko **kam shock**, **clear path**, aur **support** mile — naya stack fast hai, lekin **dimaag mein map** purane jaisa rahe jahan product ne waisa rakha hai.

---

## 1. Product alignment (pehle)

| Action | Why |
|--------|-----|
| **`LEGACY_PARITY_MAPPING.md`** matrix mein **legacy screen → `/dashboard/...`** rows (evidence ke saath) | Team ko “pehle kahan tha, ab kahan hai” ek jagah dikhe |
| **Same words** sidebar / pages par (Leads, Workboard, Wallet, …) — `dashboard-registry` labels | Muscle memory + training kam |
| **Stub screens** ke liye honest copy (“coming soon” / “beta”) — surprise nahi | Trust |

---

## 2. Pilot roster & support (assign names — Sprint 1)

| Role | Name / email | Start date | Notes |
|------|--------------|------------|-------|
| Admin pilot | *TBD — assign* | | Full nav + pool / recycle |
| Leader pilot | *TBD — assign* | | Leads + workboard + follow-ups |
| Team pilot | *TBD — assign* | | Scoped leads + wallet if applicable |

**Support channel:** *TBD — e.g. Slack `#myle-vl2-rollout` or WhatsApp group* — **owner:** *TBD*

**Escalation:** Engineering on-call or repo maintainer + product (Sam) for parity / stub questions.

---

## 3. Rollout phases (suggested)

1. **Pilot** — chhota group (admin + 1 leader + 1 team); real tasks nayi app par; feedback loop short (daily / weekly).
2. **Parallel run** (jab tak safe ho) — critical workflows dono jagah possible hon; **cutover date** announce karo.
3. **Training order** — pehle **login → Dashboard → Leads → Workboard** (80% day); phir follow-ups / pool / wallet by role.
4. **Cutover** — old app read-only ya redirect; **support window** (e.g. 2 hafte) clear rakho.

Repo technical order: **`docs/PARITY_ROLLOUT_PLAN.md`** (waves).

---

## 4. Team ko dena (templates)

- **One-pager PDF / Notion:** “New Myle — same work, new app” + screenshot 4–5 cheezon ke (dashboard, leads, workboard).
- **Role-based checklists:** Admin kya karega; Leader kya; Team kya — 5 bullets each.
- **“Pehle vs ab” table** — matrix se auto; jahan stub hai, **explicit** likho: “Abhi placeholder; date X pe full.”

---

## 5. Support & friction

| Friction | Mitigation |
|----------|------------|
| “Button kaam nahi karta” | Stub vs full — `DASHBOARD_UX_AND_PARITY.md` |
| Slow / error | API URL, cookies, `X-Request-ID` support ko forward karo |
| Role galat dikhe | **`/auth/me`** source of truth; header preview role par rely mat |

---

## 6. Owner checklist (launch se pehle)

- [ ] Parity matrix mein **top 10 flows** mapped (evidence)
- [ ] Pilot users + dates
- [ ] Training recording ya live session booked
- [ ] Support channel (Slack / WhatsApp / ticket) + owner
- [ ] Old app deprecation message + **last date**

---

## Related docs

- `LEGACY_PARITY_MAPPING.md` — mapping + evidence  
- `PARITY_ROLLOUT_PLAN.md` — implementation waves  
- `DASHBOARD_UX_AND_PARITY.md` — stubs / clicks explain  

Is playbook ko **har quarter** review karo jab nayi wave ship ho.
