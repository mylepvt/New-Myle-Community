# Production-ready + Apple-grade UX — master checklist

**Purpose:** App ko **“build / MVP shipped”** se **production-ready, daily-use, cross-device** aur **industry-level visual quality** (Apple-tier discipline: calm neutrals, system-native feel, typographic hierarchy) tak le jana.

**How to use:** Top se order mein kaam karo; har section mein `[ ]` ko `[x]` karte jao jab complete ho.

---

## A. Honest snapshot — abhi kahan ho

| Area | Abhi (typical) | Target |
|------|----------------|--------|
| **Stack** | FastAPI + Vite, Docker, CI, Render path | Same + hardened ops |
| **Theme** | Plum / wine velvet (heavy purple) | Neutral-first + **one** restrained accent (Apple-style: mostly gray/black, subtle blue or muted brand) |
| **Font** | `Plus Jakarta` in Tailwind; `index.html` loads **Inter** | **Ek** choice: Inter *ya* system stack — duplicate mat rakho |
| **Mobile** | viewport-fit, some meta tags | Safe-area, touch targets, Safari/Chrome QA matrix |
| **PWA** | Minimal `sw.js` | Optional: precache strategy jab product decide kare |

---

## B. Production-ready (backend + ops)

- [ ] **Secrets:** `SECRET_KEY` / `NEW_SECRET` strong + rotated; DB password not default  
- [ ] **`AUTH_DEV_LOGIN_ENABLED=false`** production par; dev users sirf staging  
- [ ] **`alembic upgrade head`** live DB par verified; **`GET /health/migrations`** → `at_head: true`  
- [ ] **CORS + cookies:** prod domains exact; `SameSite` / `Secure` documented  
- [ ] **Rate limits + abuse:** auth paths; optional IP allowlist for admin  
- [ ] **Backups:** Postgres automated backup + restore dry-run  
- [ ] **Observability:** error tracking (e.g. Sentry), log aggregation, uptime ping on `/health`  
- [ ] **Legal / product:** Terms, Privacy, data retention — jab public users hon  

---

## C. Cross-browser & cross-device (next-level QA)

### Matrix (har major release par smoke test)

| Client | Minimum |
|--------|---------|
| **iPhone Safari** (latest + one older iOS) | Login, dashboard scroll, sidebar, forms, WS if used |
| **Chrome Android** | Same + keyboard overlap |
| **Desktop Chrome / Edge / Firefox / Safari** | Layout break nahi, cookies, refresh token |
| **Small phone** (≤360px width) | Nav + tables/lists usable |

### Engineering checklist

- [ ] **`viewport`** already `viewport-fit=cover` — **safe-area** insets: header/sidebar/footer par `env(safe-area-inset-*)` jahan fixed UI hai  
- [ ] **Touch targets** ≥ ~44×44pt equivalent (`min-h-[44px]` / padding) primary actions par  
- [ ] **`100vh` issues** on mobile — avoid jahan bottom bar jump karta ho; `min-h-dvh` prefer (already partial)  
- [ ] **Input zoom:** iOS par 16px+ base font inputs par taaki zoom-on-focus na ho  
- [ ] **`-webkit-tap-highlight`** / focus rings — visible, theme ke saath match  
- [ ] **Service worker:** agar cache add karo to **versioned** bust + logout flow test  

---

## D. Design system — “industry / Apple-like” (theme + type)

Apple web products = **mostly neutral surfaces**, **ek** clear accent, **large readable type**, **kam saturation**, **zyada whitespace**. Wine/plum-heavy theme ko “premium” se “corporate / trustworthy” banane ke liye:

### D1. Typography (pehle yeh — sabse bada perceived upgrade)

- [ ] **Font stack align:** `tailwind.config.js` + `index.html` **same** font — recommended path:  
  - **Option A:** **Inter** (already linked in HTML) → Tailwind `fontFamily.sans` = `Inter`, `system-ui`, `sans-serif`  
  - **Option B:** Pure **system UI** (`-apple-system, BlinkMacSystemFont, "Segoe UI", …`) — fastest native feel, no Google Fonts  
- [ ] **Scale:** define explicit **type scale** (e.g. 12 / 14 / 16 / 20 / 24 / 32) — headings vs body vs captions  
- [ ] **Line-height / letter-spacing:** body `leading-relaxed`; labels `tracking-wide` sparingly  
- [ ] **Tabular nums** for counts / money: `tabular-nums` jahan digits align hon  

### D2. Colour (wine → restrained)

- [ ] **Neutrals first:** background **near-black / dark gray** (hue 0 or 220, low chroma) — not saturated purple wash  
- [ ] **Single accent:** **ek** primary (muted blue `#0A84FF` style *ya* desaturated brand) — buttons, links, active nav  
- [ ] **Remove competing glows:** kam `shadow-velvet` / purple radial; **subtle** border + **one** soft shadow tier  
- [ ] **Contrast:** WCAG **AA** minimum text on surfaces (check with DevTools / Stark)  
- [ ] **Light mode (optional):** agar product ko chahiye — same tokens `light` class se  

### D3. Motion & polish

- [ ] **`prefers-reduced-motion`:** respect karo — transitions off / minimal  
- [ ] **Duration:** 150–250ms UI, page-level heavier nahi  
- [ ] **Skeletons** loading par — already pattern hai; **consistent** rakho  

### D4. Components

- [ ] **Cards:** ek hi pattern — `surface-elevated` ya Apple-style flat `border` + `bg` (mix mat karo randomly)  
- [ ] **Inputs:** same height, radius, border colour across app  
- [ ] **Empty / error states:** copy + **ek** CTA — “dead ends” nahi  

---

## E. PWA / install / brand assets

- [ ] **`apple-touch-icon.png`** real **180×180** (not placeholder) + **`mask-icon`** optional  
- [ ] **`og-image.png`** exists + correct absolute URL prod par  
- [ ] **Manifest:** `name`, `short_name`, `theme_color` **new neutral** palette ke saath align  
- [ ] **Screenshots** (optional): App Store–style for marketing PWA  

---

## F. Performance (feel “next level”)

- [ ] **Lighthouse** (mobile): Performance / Accessibility / Best Practices targets set karo (e.g. A11y ≥ 90)  
- [ ] **Bundle:** route-level code split (already lazy dashboard) — **heavy** routes verify  
- [ ] **Images:** `width`/`height`, lazy load, WebP where needed  
- [ ] **API:** list endpoints paginated; avoid huge JSON on mobile  

---

## G. Security & privacy (production bar)

- [ ] **Cookies:** `HttpOnly`, `Secure`, `SameSite` documented  
- [ ] **CSRF** strategy if non-cookie clients add ho  
- [ ] **Headers:** `Content-Security-Policy` gradual tighten  
- [ ] **Dependency audit:** `npm audit`, Python advisory check on schedule  

---

## H. Definition of “done” for this checklist

**Production-ready:** B + G minimum + Render/env verified + smoke matrix on C.  
**Apple-grade UX:** D complete (typography + neutral palette + single accent) + C mobile pass + F Lighthouse targets met.

---

## Quick wins (1–2 days, high impact)

1. **Unify font:** Tailwind = Inter **or** remove Inter link and use system stack — **don’t load two sans fonts.**  
2. **Desaturate background** — pull purple out of `--background`; keep accent only for **primary + active nav**.  
3. **Safe-area** padding on dashboard header + bottom nav (agar future mein add ho).  
4. **Real `apple-touch-icon`** + **`theme-color`** match new neutral bg.

---

_Last created: 2026-04-11 — align with `MYLE_VL2_ROADMAP.md` when phases advance._
