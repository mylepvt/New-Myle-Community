# Myle vl2 — Production Roadmap
## Senior Architect Analysis: Build Shell → Production

**Date:** 2026-04-11  
**Analyst:** Senior System Architect (Claude)  
**Status:** vl2 is a well-structured shell. Old app has 3 years of business logic. This doc bridges them.

---

## PART 0 — HONEST REALITY CHECK

### What vl2 is RIGHT NOW
A clean, modern, deployable shell. Auth works. Basic lead CRUD works. WebSocket works. CI/CD works. Design system works.

### What the old app HAS that vl2 DOES NOT
The old app is a **complete sales training + network MLM platform** with:
- 78 HTML templates, ~500KB of business logic
- 15 database tables
- Full Day1 → Day2 → Day3 → Track → Seat Hold → Conversion funnel
- Wallet + pool pricing engine
- Discipline / performance enforcement system
- AI coaching integration
- Training video series + MCQ test + PDF certificates
- Gamification (points, badges, leaderboards)
- Org hierarchy with upline/downline
- Scheduled auto-expire, stale redistribution

**Gap = ~85% of business features.**

---

## PART 1 — COMPLETE FEATURE INVENTORY

### OLD APP → vl2 STATUS TABLE

| Feature | Old App | vl2 Now | Gap Level |
|---------|---------|---------|-----------|
| Auth (login/logout) | ✅ | ✅ | NONE |
| Role system (admin/leader/team) | ✅ | ✅ partial | LOW |
| Lead CRUD | ✅ | ✅ | LOW |
| Lead search + filter | ✅ | ✅ | LOW |
| Lead archive/restore | ✅ | ✅ | NONE |
| Lead delete/recycle | ✅ | ✅ | NONE |
| Lead pool (browse + claim) | ✅ | ✅ partial | MEDIUM |
| Follow-ups | ✅ | ✅ | LOW |
| Workboard (kanban) | ✅ | ✅ partial | MEDIUM |
| Wallet (balance + ledger) | ✅ | ✅ partial | MEDIUM |
| Retarget | ✅ | ✅ | LOW |
| Team members list | ✅ | ✅ | LOW |
| Real-time (WebSocket) | ✅ | ✅ | NONE |
| **Phone + email on leads** | ✅ | ❌ MISSING | **CRITICAL** |
| **Call tracking (status, count, tags)** | ✅ | ❌ MISSING | **CRITICAL** |
| **Day1/Day2/Day3 funnel** | ✅ | ❌ MISSING | **CRITICAL** |
| **₹196 payment proof + approval** | ✅ | ❌ MISSING | **CRITICAL** |
| **Enrollment / video sharing** | ✅ | ❌ MISSING | **CRITICAL** |
| **Video watch tracking** | ✅ | ❌ MISSING | **CRITICAL** |
| **7-day training video series** | ✅ | ❌ MISSING | **HIGH** |
| **MCQ test (30 questions, cert)** | ✅ | ❌ MISSING | **HIGH** |
| **Track selection (Slow/Med/Fast)** | ✅ | ❌ MISSING | **HIGH** |
| **Seat hold system** | ✅ | ❌ MISSING | **HIGH** |
| **Wallet recharge (UTR + proof)** | ✅ | ❌ MISSING | **HIGH** |
| **Dynamic pool pricing per lead** | ✅ | ❌ MISSING | **HIGH** |
| **Gamification (points, badges)** | ✅ | ❌ MISSING | **HIGH** |
| **Daily reports (15-call target)** | ✅ | ❌ MISSING | **HIGH** |
| **Leaderboard** | ✅ | ❌ stub | **HIGH** |
| **Org tree / upline hierarchy** | ✅ | ❌ MISSING | **HIGH** |
| **Auto-expire scheduler (24h rule)** | ✅ | ❌ MISSING | **HIGH** |
| **Discipline engine (inactivity)** | ✅ | ❌ MISSING | **HIGH** |
| **Stale lead redistribution** | ✅ | ❌ MISSING | **HIGH** |
| **AI coaching (per lead)** | ✅ | ❌ placeholder | **MEDIUM** |
| **Admin KPI dashboard** | ✅ | ❌ MISSING | **MEDIUM** |
| **Performance scoring + streaks** | ✅ | ❌ MISSING | **MEDIUM** |
| **Push notifications** | ✅ | ❌ minimal SW | **MEDIUM** |
| **Announcements / notice board** | ✅ | ❌ stub | **MEDIUM** |
| **Batch video slots (Day2)** | ✅ | ❌ MISSING | **MEDIUM** |
| **Day2 certificate PDF** | ✅ | ❌ MISSING | **MEDIUM** |
| **Email (welcome, reset)** | ✅ | ❌ MISSING | **LOW** |
| **UPI QR for recharge** | ✅ | ❌ MISSING | **LOW** |
| **Grace request system** | ✅ | ❌ MISSING | **LOW** |
| **FBO ID / upline lookup** | ✅ | ❌ MISSING | **LOW** |
| **Market cold detection** | ✅ | ❌ MISSING | **LOW** |
| **At-risk / stale lead alerts** | ✅ | ❌ MISSING | **LOW** |

---

## PART 2 — DATABASE GAP (MODEL FIELDS TO ADD)

### 2.1 Lead Model — Missing Fields

```python
# vl2 current Lead fields:
# id, name, status, created_by_user_id, created_at, archived_at, deleted_at, in_pool

# MUST ADD — Phase 1 (core workflow):
phone:               str | None   # Primary contact. Normalize: +91XXXXXXXXXX
email:               str | None   # Optional contact
call_status:         str          # Enum: not_called, no_answer, interested, not_interested,
                                  #       follow_up, switch_off, busy, call_back, wrong_number
contact_count:       int = 0      # How many times called
last_contacted_at:   datetime | None
follow_up_at:        datetime | None    # Scheduled follow-up date+time
source:              str | None   # How lead came in
pipeline_stage:      str          # prospecting | enrolled | day1 | day2 | day3 |
                                  # track_selected | seat_hold | closing | complete | lost

# MUST ADD — Phase 2 (funnel):
payment_done:        bool = False
payment_amount:      int = 0      # In paise (₹196 = 19600)
payment_proof_path:  str | None   # S3/filesystem path for screenshot
payment_approved_by: int | None   # user_id of leader who approved
payment_approved_at: datetime | None
day1_done:           bool = False
day2_done:           bool = False
interview_done:      bool = False
d1_morning:          bool = False  # Day1 batch attendance
d1_afternoon:        bool = False
d1_evening:          bool = False
d2_morning:          bool = False  # Day2 batch attendance
d2_afternoon:        bool = False
d2_evening:          bool = False
interview_status:    str | None   # cleared | not_cleared
track_selected:      str | None   # slow | medium | fast
track_price:         int | None   # In paise
seat_hold_amount:    int | None   # In paise
seat_hold_expiry:    datetime | None
assigned_to_user_id: int | None   # Current executor (can differ from created_by after pool claim)
pool_price:          int | None   # Price when added to pool (paise)
claimed_at:          datetime | None
current_owner_id:    int | None   # Original buyer (for wallet debit tracking)
flow_started_at:     datetime | None  # When Paid ₹196 happened (Day1 timer starts)
pipeline_entered_at: datetime | None

# OPTIONAL — Phase 3:
follow_up_missed_count:    int = 0
no_response_attempt_count: int = 0
test_status:               str | None  # not_attempted | passed | failed
test_score:                int | None
test_attempts:             int = 0
notes:                     str | None   # Quick note field
```

### 2.2 User Model — Missing Fields

```python
# vl2 current User fields:
# id, email, role, hashed_password, created_at

# MUST ADD — Phase 1:
status:              str = 'approved'   # pending | approved | rejected
upline_user_id:      int | None         # Who referred/manages this user
fbo_id:              str | None         # Network unique ID
display_name:        str | None

# MUST ADD — Phase 2:
total_points:        int = 0
user_stage:          str = 'active'     # active | training | suspended
training_required:   bool = False
training_status:     str = 'not_started' # not_started | in_progress | completed
calling_reminder_time: str | None       # HH:MM format

# OPTIONAL — Phase 3:
badges_json:         str = '[]'         # JSON array of earned badge keys
last_active_at:      datetime | None
```

### 2.3 New Tables to Create

```sql
-- Call tracking per lead (append-only)
CREATE TABLE call_events (
    id           INTEGER PRIMARY KEY,
    lead_id      INTEGER NOT NULL REFERENCES leads(id),
    user_id      INTEGER NOT NULL REFERENCES users(id),
    call_result  TEXT NOT NULL,   -- no_answer | interested | not_interested | etc.
    note         TEXT,
    called_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Training videos (Day 1-7 content)
CREATE TABLE training_videos (
    id           INTEGER PRIMARY KEY,
    day_number   INTEGER NOT NULL CHECK(day_number BETWEEN 1 AND 7),
    youtube_url  TEXT,
    pdf_url      TEXT,
    title        TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Training progress per user
CREATE TABLE training_progress (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    day_number   INTEGER NOT NULL,
    completed    BOOLEAN DEFAULT 0,
    completed_at TIMESTAMP,
    UNIQUE(user_id, day_number)
);

-- MCQ test questions
CREATE TABLE training_questions (
    id           INTEGER PRIMARY KEY,
    question     TEXT NOT NULL,
    option_a     TEXT NOT NULL,
    option_b     TEXT NOT NULL,
    option_c     TEXT NOT NULL,
    option_d     TEXT NOT NULL,
    correct      TEXT NOT NULL,   -- 'a' | 'b' | 'c' | 'd'
    sort_order   INTEGER DEFAULT 0
);

-- MCQ test attempts
CREATE TABLE training_test_attempts (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    score        INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    passed       BOOLEAN NOT NULL,
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily reports
CREATE TABLE daily_reports (
    id                INTEGER PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    report_date       DATE NOT NULL,
    total_calls       INTEGER DEFAULT 0,
    pdfs_covered      INTEGER DEFAULT 0,
    calls_picked      INTEGER DEFAULT 0,
    enrollments_done  INTEGER DEFAULT 0,
    wrong_numbers     INTEGER DEFAULT 0,
    remarks           TEXT,
    submitted_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, report_date)
);

-- Wallet recharge requests
CREATE TABLE wallet_recharges (
    id              INTEGER PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    amount_cents    INTEGER NOT NULL,
    utr_number      TEXT NOT NULL,
    proof_path      TEXT,
    status          TEXT DEFAULT 'pending',  -- pending | approved | rejected
    reviewed_by_id  INTEGER REFERENCES users(id),
    reviewed_at     TIMESTAMP,
    idempotency_key TEXT UNIQUE NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Enrollment links (video sharing)
CREATE TABLE enrollment_links (
    id           INTEGER PRIMARY KEY,
    lead_id      INTEGER NOT NULL REFERENCES leads(id),
    shared_by_id INTEGER NOT NULL REFERENCES users(id),
    token        TEXT UNIQUE NOT NULL,   -- Public token for watch URL
    watch_url    TEXT NOT NULL,
    sent_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    watched_at   TIMESTAMP,
    watch_count  INTEGER DEFAULT 0
);

-- Announcements
CREATE TABLE announcements (
    id           INTEGER PRIMARY KEY,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL,
    created_by_id INTEGER REFERENCES users(id),
    pinned       BOOLEAN DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Badges
CREATE TABLE user_badges (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    badge_key    TEXT NOT NULL,
    unlocked_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, badge_key)
);

-- Audit log (expand existing activity concept)
CREATE TABLE audit_log (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id),
    action       TEXT NOT NULL,   -- lead.status_changed | wallet.adjusted | etc.
    entity_type  TEXT,            -- lead | user | wallet | etc.
    entity_id    INTEGER,
    before_state TEXT,            -- JSON snapshot
    after_state  TEXT,            -- JSON snapshot
    ip_address   TEXT,
    user_agent   TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## PART 3 — EVENT-DRIVEN ARCHITECTURE

### 3.1 Core Event Taxonomy

Every user action fires one immutable, idempotent event. Events are the source of truth for audit, analytics, and side-effects.

```
Domain: LEAD
──────────────────────────────────────────────────────
lead.created          → {lead_id, name, phone, email, created_by, source}
lead.assigned         → {lead_id, from_user_id, to_user_id, by_user_id}
lead.status_changed   → {lead_id, from_status, to_status, by_user_id, reason}
lead.stage_changed    → {lead_id, from_stage, to_stage, by_user_id}
lead.archived         → {lead_id, by_user_id}
lead.restored         → {lead_id, by_user_id}
lead.deleted          → {lead_id, by_user_id}
lead.added_to_pool    → {lead_id, pool_price_paise, by_user_id}
lead.claimed          → {lead_id, claimed_by_user_id, cost_paise, idempotency_key}
lead.expired          → {lead_id, expired_stage, triggered_by: 'scheduler'}
lead.redistributed    → {lead_id, from_user_id, to_user_id, reason: 'stale'}

Domain: CALL
──────────────────────────────────────────────────────
call.attempted        → {lead_id, by_user_id, result, note, called_at}
call.target_met       → {user_id, date, call_count}
call.target_missed    → {user_id, date, call_count, penalty_applied}

Domain: ENROLLMENT
──────────────────────────────────────────────────────
enrollment.link_generated  → {lead_id, by_user_id, token, channel: 'whatsapp'|'sms'}
enrollment.video_sent      → {lead_id, by_user_id, token}
enrollment.video_watched   → {lead_id, token, watched_at, ip_address}

Domain: PAYMENT
──────────────────────────────────────────────────────
payment.proof_uploaded     → {lead_id, by_user_id, proof_path, amount_paise}
payment.proof_approved     → {lead_id, approved_by_user_id, amount_paise}
payment.proof_rejected     → {lead_id, rejected_by_user_id, reason}
payment.recorded           → {lead_id, amount_paise, type: 'enrollment'|'track'|'seat_hold'}

Domain: FUNNEL (Day1/Day2/Day3)
──────────────────────────────────────────────────────
funnel.day1_started        → {lead_id, by_user_id}
funnel.day1_batch_done     → {lead_id, batch_slot, by_user_id}  # morning|afternoon|evening
funnel.day2_started        → {lead_id, by_user_id}
funnel.day2_batch_done     → {lead_id, batch_slot, by_user_id}
funnel.day2_test_link_sent → {lead_id, token, by_user_id}
funnel.day2_test_submitted → {lead_id, score, total, passed, attempted_at}
funnel.day3_interview_done → {lead_id, status: 'cleared'|'not_cleared', by_user_id}
funnel.track_selected      → {lead_id, track: 'slow'|'medium'|'fast', price_paise, by_user_id}
funnel.seat_hold_placed    → {lead_id, amount_paise, expiry_at, by_user_id}
funnel.converted           → {lead_id, final_amount_paise, by_user_id}

Domain: WALLET
──────────────────────────────────────────────────────
wallet.recharge_requested  → {user_id, amount_paise, utr_number, proof_path, idempotency_key}
wallet.recharge_approved   → {user_id, request_id, amount_paise, approved_by_id}
wallet.recharge_rejected   → {user_id, request_id, reason, rejected_by_id}
wallet.pool_debit          → {user_id, lead_id, amount_paise, idempotency_key}
wallet.admin_adjustment    → {user_id, amount_paise, reason, by_user_id, idempotency_key}

Domain: TRAINING
──────────────────────────────────────────────────────
training.day_unlocked      → {user_id, day_number, unlocked_at}
training.video_watched     → {user_id, day_number, watched_at}
training.test_submitted    → {user_id, score, passed, attempt_number}
training.certificate_issued→ {user_id, lead_id, certificate_path}
training.completed         → {user_id, completed_at}

Domain: REPORTING
──────────────────────────────────────────────────────
report.submitted           → {user_id, date, calls, enrollments, pdfs}
report.call_target_checked → {user_id, date, target_met: bool}

Domain: USER
──────────────────────────────────────────────────────
user.registered            → {user_id, email, role, upline_user_id, fbo_id}
user.approved              → {user_id, approved_by_id}
user.rejected              → {user_id, rejected_by_id, reason}
user.stage_changed         → {user_id, from_stage, to_stage}
user.badge_earned          → {user_id, badge_key}
user.points_updated        → {user_id, delta, reason, new_total}
user.grace_requested       → {user_id, reason, request_date}
user.inactivity_warned     → {user_id, tier: '24h'|'48h'|'72h'}

Domain: SYSTEM
──────────────────────────────────────────────────────
system.scheduler_run       → {job: 'auto_expire'|'stale_redistribute', affected_count, run_at}
system.announcement_posted → {announcement_id, by_user_id}
```

### 3.2 Event Schema Standard

```typescript
// Every event conforms to this envelope
interface MyleEvent<T = Record<string, unknown>> {
  event_id:      string;          // UUIDv4 — unique forever
  event_name:    string;          // e.g. "lead.status_changed"
  event_version: number;          // Schema version for forward compat
  idempotency_key: string;        // Dedup key (see Part 5)
  actor: {
    user_id:     number;
    role:        'admin' | 'leader' | 'team';
    ip_address:  string;
  };
  payload:       T;               // Domain-specific fields
  occurred_at:   string;          // ISO 8601 UTC
  source:        'api' | 'scheduler' | 'webhook' | 'admin_override';
}
```

---

## PART 4 — LEAD STATE MACHINE

### 4.1 All States

```
PROSPECTING STATES
──────────────────
new            → Just created. No contact yet.
contacted      → At least one call made.
invited        → Physically/virtually invited to session.
video_sent     → Video link shared (enrollment token generated).
video_watched  → Prospect opened the watch URL.

ENROLLMENT GATE
───────────────
paid_196       → ₹196 payment uploaded + approved by leader.
               → This is the GATE. Everything before = free pipeline.
               → Everything after = paid funnel.

FUNNEL STAGES (post-payment)
─────────────────────────────
day1           → Attending Day 1 group session.
day2           → Attending Day 2 evaluation.
day3           → Interview stage.
track_selected → Has chosen Slow/Medium/Fast track.
seat_hold      → Interim payment placed to hold seat.
closing        → Final conversion in progress.

TERMINAL STATES
───────────────
converted      → Fully enrolled + track paid.
lost           → Cold/dropped. Can be retargeted.
retarget       → Marked for re-engagement.
inactive       → Auto-expired (24h rule). Scheduleronly.
```

### 4.2 Allowed Transitions (State Machine)

```
FROM          → TO                    ROLES ALLOWED        TRIGGER
────────────────────────────────────────────────────────────────────────────
new           → contacted             team, leader, admin  manual
new           → invited               team, leader, admin  manual
new           → lost                  team, leader, admin  manual
new           → retarget              team, leader, admin  manual

contacted     → invited               team, leader, admin  manual
contacted     → video_sent            team, leader, admin  manual
contacted     → lost                  team, leader, admin  manual
contacted     → retarget              team, leader, admin  manual

invited       → video_sent            team, leader, admin  manual
invited       → contacted             team, leader, admin  manual
invited       → lost                  team, leader, admin  manual

video_sent    → video_watched         SYSTEM ONLY          auto (watch event)
video_sent    → lost                  team, leader, admin  manual

video_watched → paid_196              team, leader, admin  manual (after approval)
video_watched → lost                  team, leader, admin  manual
video_watched → retarget              team, leader, admin  manual
video_watched → inactive              SYSTEM ONLY          auto (24h expire)

paid_196      → day1                  leader, admin        manual (Day1 routing)
paid_196      → lost                  admin ONLY           override

day1          → day2                  leader, admin        manual (after d1 batches done)
day1          → inactive              SYSTEM ONLY          auto (24h no activity)
day1          → lost                  admin ONLY           override

day2          → day3                  leader, admin        manual (after test pass)
day2          → inactive              SYSTEM ONLY          auto (24h no activity)

day3          → track_selected        leader, admin        manual
day3          → inactive              SYSTEM ONLY          auto (24h)

track_selected→ seat_hold             leader, admin        manual
track_selected→ closing               leader, admin        manual (if no seat hold)
track_selected→ inactive              SYSTEM ONLY          auto (24h)

seat_hold     → closing               leader, admin        manual
seat_hold     → inactive              SYSTEM ONLY          auto (24h if no seat payment)

closing       → converted             admin ONLY           manual (final gate)

inactive      → new                   admin ONLY           override
inactive      → contacted             leader, admin        re-engage
retarget      → contacted             team, leader, admin  manual
lost          → retarget              leader, admin        manual

# FORBIDDEN TRANSITIONS (hard reject at API level):
# new → paid_196         (must go through video_watched first)
# new → day1             (must have paid_196)
# team → paid_196        (team can log the status but LEADER must approve proof)
# any → converted        (admin only, no skipping)
# converted → anything   (terminal — immutable)
```

### 4.3 Backend Enforcement (Python)

```python
# backend/app/services/lead_state_machine.py

ALLOWED_TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "new":            {"team":  {"contacted","invited","lost","retarget"},
                       "leader":{"contacted","invited","video_sent","lost","retarget"},
                       "admin": {"contacted","invited","video_sent","paid_196","day1","lost","retarget"}},
    "contacted":      {"team":  {"invited","video_sent","lost","retarget"},
                       "leader":{"invited","video_sent","lost","retarget"},
                       "admin": {"invited","video_sent","paid_196","lost","retarget"}},
    "video_watched":  {"system":{"paid_196","inactive"},  # system auto-transitions
                       "team":  {"lost","retarget"},
                       "leader":{"paid_196","lost","retarget"},
                       "admin": {"paid_196","day1","lost","retarget","inactive"}},
    "paid_196":       {"leader":{"day1"},
                       "admin": {"day1","lost"}},
    "day1":           {"leader":{"day2"},
                       "admin": {"day2","lost"},
                       "system":{"inactive"}},
    "day2":           {"leader":{"day3"},
                       "admin": {"day3","lost"},
                       "system":{"inactive"}},
    "day3":           {"leader":{"track_selected"},
                       "admin": {"track_selected","closing","lost"},
                       "system":{"inactive"}},
    "track_selected": {"leader":{"seat_hold","closing"},
                       "admin": {"seat_hold","closing","lost"},
                       "system":{"inactive"}},
    "seat_hold":      {"leader":{"closing"},
                       "admin": {"closing","lost"},
                       "system":{"inactive"}},
    "closing":        {"admin": {"converted","lost"}},
    "inactive":       {"admin": {"new","contacted"},
                       "leader":{"contacted","retarget"}},
    "retarget":       {"team":  {"contacted","new"},
                       "leader":{"contacted","new"},
                       "admin": {"contacted","new","lost"}},
    "lost":           {"leader":{"retarget"},
                       "admin": {"retarget","new"}},
    "converted":      {},  # TERMINAL — no transitions allowed
}

def validate_transition(from_status: str, to_status: str, role: str) -> bool:
    allowed = ALLOWED_TRANSITIONS.get(from_status, {})
    role_allowed = allowed.get(role, set()) | allowed.get("admin", set()) if role == "admin" else allowed.get(role, set())
    if to_status not in role_allowed:
        raise ValueError(f"Transition {from_status}→{to_status} not allowed for role={role}")
    return True
```

---

## PART 5 — IDEMPOTENCY + DUPLICATION CONTROL

### 5.1 Idempotency Key Strategy

```
Event                  Key Formula                              Storage
──────────────────────────────────────────────────────────────────────────────
wallet.pool_debit      SHA256(user_id + lead_id + "pool_debit") wallet_ledger.idempotency_key (UNIQUE)
wallet.recharge_req    user_id + UTR_number                     wallet_recharges.idempotency_key (UNIQUE)
wallet.adjustment      UUID from client                         wallet_ledger.idempotency_key (UNIQUE)
lead.claimed           user_id + lead_id + "claim"              leads.claimed_idempotency_key
enrollment.link_gen    lead_id + user_id + date(day)            enrollment_links token (UNIQUE)
payment.recorded       lead_id + "payment_196"                  leads.payment_idempotency_key
funnel.batch_done      lead_id + batch_slot                     leads boolean column (idempotent by nature)
report.submitted       user_id + report_date                    daily_reports UNIQUE(user_id, report_date)
training.test_submit   user_id + attempt_number                 training_test_attempts
```

### 5.2 Duplicate Lead Prevention

```python
# Normalize phone before insert
def normalize_phone(raw: str) -> str:
    digits = re.sub(r'\D', '', raw)
    if digits.startswith('91') and len(digits) == 12:
        return '+' + digits
    if len(digits) == 10:
        return '+91' + digits
    raise ValueError(f"Invalid phone: {raw}")

# Duplicate check (soft — warn, not hard block to avoid false positives)
async def check_duplicate_lead(db, phone: str, created_by: int) -> LeadPublic | None:
    norm = normalize_phone(phone)
    existing = await db.execute(
        "SELECT id, name, status FROM leads WHERE phone=? AND deleted_at IS NULL", (norm,)
    )
    return existing.fetchone()
```

### 5.3 Wallet Double-Credit Prevention

```sql
-- wallet_ledger has UNIQUE idempotency_key
-- Any attempt to insert same key raises IntegrityError → return existing row (not error)

INSERT INTO wallet_ledger (user_id, amount_cents, reason, idempotency_key)
VALUES (?, ?, ?, ?)
ON CONFLICT(idempotency_key) DO NOTHING
RETURNING *;

-- If 0 rows returned → was duplicate → fetch existing and return 200 (not 201)
```

---

## PART 6 — ROLE-BASED ACCESS CONTROL (RBAC)

### 6.1 Roles Definition

```
ADMIN     → God mode. Full data access. Can override any state. Has audit trail.
LEADER    → Team scoped. Manages downline. Approves payments. Cannot modify wallet directly.
TEAM      → Lead scoped. Can only act on assigned leads. Cannot see team-wide data.
```

### 6.2 Data Scoping (Backend Enforced — NOT frontend)

```python
# backend/app/core/data_scope.py

def apply_lead_scope(query: Select, user: UserSession) -> Select:
    """Every lead query MUST pass through this."""
    if user.role == "admin":
        return query  # All leads, no filter
    elif user.role == "leader":
        # Leader sees: their own leads + their direct downline's leads
        downline_ids = get_downline_user_ids(user.id)
        return query.where(Lead.created_by_user_id.in_([user.id] + downline_ids))
    else:  # team
        # Team sees: only leads they created OR leads assigned to them
        return query.where(
            or_(
                Lead.created_by_user_id == user.id,
                Lead.assigned_to_user_id == user.id
            )
        )

def apply_wallet_scope(query: Select, user: UserSession) -> Select:
    if user.role == "admin":
        return query
    # Leader/Team can only see their own wallet
    return query.where(WalletLedgerEntry.user_id == user.id)

def apply_user_scope(query: Select, user: UserSession) -> Select:
    if user.role == "admin":
        return query
    elif user.role == "leader":
        downline_ids = get_downline_user_ids(user.id)
        return query.where(User.id.in_([user.id] + downline_ids))
    else:
        return query.where(User.id == user.id)
```

### 6.3 Permission Matrix

```
Action                              admin  leader  team
──────────────────────────────────────────────────────────────────
View all leads                        ✅      ❌      ❌
View team leads (downline)            ✅      ✅      ❌
View own leads                        ✅      ✅      ✅
Create lead                           ✅      ✅      ✅
Edit lead (prospecting statuses)      ✅      ✅      ✅
Move to Day1/Day2/Day3                ✅      ✅      ❌
Approve ₹196 payment proof            ✅      ✅      ❌
Mark converted (final)                ✅      ❌      ❌
Override any state                    ✅      ❌      ❌
Delete lead (soft)                    ✅      ❌      ❌
Restore deleted lead                  ✅      ❌      ❌
Add to pool                           ✅      ❌      ❌
Set pool price                        ✅      ❌      ❌
Claim from pool                       ✅      ✅      ✅ (gate: wallet balance + proof approval)
View wallet (own)                     ✅      ✅      ✅
Request wallet recharge               ✅      ✅      ✅
Approve wallet recharge               ✅      ❌      ❌
Manual wallet adjustment              ✅      ❌      ❌
Approve user registration             ✅      ❌      ❌
View all users                        ✅      ✅ (team only) ❌
Manage org tree/upline                ✅      ❌      ❌
Add training videos                   ✅      ❌      ❌
Manage MCQ questions                  ✅      ❌      ❌
View daily reports (all)              ✅      ✅ (team only) ❌
Submit daily report                   ✅      ✅      ✅
Post announcements                    ✅      ❌      ❌
View audit log                        ✅      ❌      ❌
Access AI coaching                    ✅      ✅      ✅ (own leads only)
Force re-trigger events               ✅      ❌      ❌
View KPI dashboard                    ✅      ✅ (limited) ❌
Manage app settings                   ✅      ❌      ❌
```

### 6.4 Ownership Engine

```python
class LeadOwnership:
    created_by_user_id:  int  # IMMUTABLE after creation
    assigned_to_user_id: int  # MUTABLE — changes on Day1 handoff or pool claim
    current_owner_id:    int  # IMMUTABLE after pool claim — for wallet debit tracking

# Rules:
# 1. Only assigned_to_user_id can update lead status (team role)
# 2. Leader can reassign within their downline
# 3. Admin can reassign to anyone
# 4. current_owner_id never changes once set (financial integrity)
# 5. Pool claim: sets both assigned_to and current_owner atomically

async def can_act_on_lead(user: UserSession, lead: Lead) -> bool:
    if user.role == "admin":
        return True
    if user.role == "leader":
        downline = get_downline_user_ids(user.id)
        return lead.created_by_user_id in downline or lead.assigned_to_user_id in downline
    # team
    return lead.assigned_to_user_id == user.id or lead.created_by_user_id == user.id
```

---

## PART 7 — FAILURE HANDLING

### 7.1 Retry + Exponential Backoff

```python
# backend/app/core/retry.py

import asyncio, random

async def with_retry(fn, max_retries=3, base_delay=1.0):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except (TransientError, DatabaseLocked) as e:
            last_exc = e
            if attempt == max_retries:
                break
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)
    raise last_exc  # Dead letter after max retries

# Retry for: scheduler jobs, wallet debits, webhook dispatches
# DO NOT retry: validation errors, auth failures, duplicate key errors
```

### 7.2 Dead Letter Queue (SQLite-based for now)

```sql
CREATE TABLE failed_events (
    id           INTEGER PRIMARY KEY,
    event_name   TEXT NOT NULL,
    payload      TEXT NOT NULL,  -- JSON
    error        TEXT NOT NULL,
    attempts     INTEGER DEFAULT 0,
    last_attempt TIMESTAMP,
    resolved     BOOLEAN DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 7.3 Partial Failure Recovery

```
Scenario: Pool claim succeeds wallet debit but fails lead assignment
  → wallet_ledger row written (has idempotency_key)
  → lead.assigned_to not updated
  Recovery: Scheduler checks for wallet debits with no matching lead.claimed_at
  → Re-runs lead assignment (idempotent — same result)
  → Fires lead.claimed event

Scenario: Enrollment link generated but video watch webhook fails to update status
  → enrollment_links.watched_at is set
  → lead.status still video_sent
  Recovery: Scheduler polls enrollment_links.watched_at IS NOT NULL + lead.status = video_sent
  → Fires enrollment.video_watched event → status updates to video_watched
```

---

## PART 8 — SHADOW MODE TESTING PLAN

```
Phase: Shadow Mode (Week 1-2)
  Old app = PRIMARY (writes go here)
  New app = SHADOW (reads old DB via replica, no writes)
  
  Compare every 15 minutes:
  - Lead count by status
  - Wallet balance by user
  - Payment count
  - Status transitions in last hour

  Mismatch threshold: >2% difference = alert

Phase: Dual Write (Week 3-4)  
  Old app = PRIMARY writes
  New app = ALSO writes (parallel)
  Compare results — new app must match old app within 100ms

Phase: Cutover (Week 5+)
  New app = PRIMARY
  Old app = READ-ONLY for 2 weeks (rollback buffer)
```

---

## PART 9 — GRADUAL ROLLOUT PLAN

```
Day 1-7:    Internal team (5 users) — dog-food testing
Week 2:     10% of active users → monitor error rates, webhook lag
Week 3:     50% of users → A/B split by user_id % 2
Week 4:     90% → keep 10% on old app as control group  
Week 5:     100% cutover
Week 7:     Old app shut down

Rollback: Feature flag ROLLBACK_TO_OLD=true in app_settings
  → Nginx rewrites all traffic back to old app in 30 seconds
  → No data loss because old DB never paused writes
```

---

## PART 10 — PRODUCTION CHECKLIST (Priority Order)

### 🔴 P0 — CRITICAL (App doesn't work without these)

- [ ] **Lead phone + email fields** — Add to Lead model + DB migration + API
- [ ] **Call status tracking** — call_status field on Lead + call_events table
- [ ] **₹196 payment proof upload** — File upload endpoint (S3 or Render disk)
- [ ] **Payment proof approval flow** — Leader reviews screenshot → approves → status gates
- [ ] **Wallet recharge request** — UTR + optional screenshot upload → pending approval
- [ ] **Wallet recharge approval (admin)** — Review pending requests → approve/reject
- [ ] **Lead pool dynamic pricing** — pool_price per lead, not flat
- [ ] **Claim gates** — Wallet balance check, proof approval check, daily limit
- [ ] **State machine enforcement at API** — Reject invalid transitions at backend
- [ ] **Data scope enforcement** — All lead queries filter by role at SQL level
- [ ] **Assigned_to field** — Who is currently responsible for this lead
- [ ] **Admin dashboard KPIs** — Total leads, conversions, revenue, at-risk count

### 🟠 P1 — HIGH (Core business flow blocked without these)

- [ ] **Day1 pipeline stage + batch tracking** — d1_morning/afternoon/evening checkboxes
- [ ] **Day2 pipeline stage + batch tracking** — d2_* checkboxes + batch video URLs
- [ ] **Day2 MCQ test system** — 30 questions, 2 attempts, pass=18/30, certificate PDF
- [ ] **Day3 interview marking** — interview_done + interview_status
- [ ] **Track selection** — Slow/Medium/Fast + track_price
- [ ] **Seat hold** — seat_hold_amount + expiry
- [ ] **Enrollment / video sharing** — Generate token URL, WhatsApp share button
- [ ] **Video watch tracking** — Public URL that sets lead.status = video_watched
- [ ] **Auto-expire scheduler** — APScheduler or Celery: leads stuck in day1/day2/day3 > 24h → inactive
- [ ] **Org tree / upline system** — upline_user_id on User, hierarchy queries
- [ ] **User registration approval flow** — pending → admin approves → welcome email
- [ ] **FBO ID system** — fbo_id on User, upline lookup by FBO at registration

### 🟡 P2 — MEDIUM (Important for adoption but not day-one blockers)

- [ ] **Training video series** (Day 1-7) — Admin can add videos, users watch + track progress
- [ ] **Training unlock calendar** — Day N unlocks on Day1_date + N-1 days
- [ ] **7-day training MCQ** — Separate from Day2 test. User training gate.
- [ ] **Daily reports** — One form per day per member: calls, PDFs, enrollments, remarks
- [ ] **Call target enforcement** — 15 calls/day minimum, daily score calculation
- [ ] **Performance scoring** — Points: call(5), video_sent(10), enrolled(25), converted(50)
- [ ] **Leaderboard** — Rank by points, conversions, this month
- [ ] **Gamification badges** — First Sale, Century, ₹1960 Club, etc.
- [ ] **Discipline engine** — 24h warning, 48h claim block, 72h full lock
- [ ] **Grace request system** — Max 2 per 30 days
- [ ] **Stale lead redistribution** — Admin tool to reassign >7-day untouched leads
- [ ] **Announcements** — Admin posts, team sees on dashboard homepage
- [ ] **Admin at-risk/stale lead alerts** — Dashboard tiles with counts + lists
- [ ] **Push notifications** — Web push on follow-up due, payment approved, etc.

### 🟢 P3 — LOW (Nice to have, post-launch)

- [ ] **AI coaching per lead** — Claude integration: tips, next action, heat score
- [ ] **AI chat with lead context** — Ask Claude about a specific lead
- [ ] **PDF certificate generation** — Day 2 test certificate (reportlab)
- [ ] **UPI QR code** — Dynamic QR for wallet recharge payment
- [ ] **Email notifications** — Welcome on approval, password reset
- [ ] **Market cold detection** — >55% no-answer rate in 5 days = alert
- [ ] **Grace period soft enforcement** — Demerits for repeated missed follow-ups
- [ ] **Bonus training videos** — Optional content beyond Day 7
- [ ] **Export to PDF/CSV** — Admin data export

---

## PART 11 — BACKEND IMPLEMENTATION ORDER

```
Sprint 1 (Week 1-2): FOUNDATION
  backend:
    ✦ Alembic migration: add phone, email, call_status, contact_count, assigned_to_user_id,
                         payment_done, payment_amount, payment_proof_path, pipeline_stage
    ✦ Create: call_events, wallet_recharges, audit_log tables
    ✦ State machine service (validate_transition)
    ✦ Data scope middleware (apply_lead_scope on all lead queries)
    ✦ File upload endpoint: POST /api/v1/files/upload → returns path
    ✦ Payment proof endpoints: POST /api/v1/leads/{id}/payment-proof, PATCH approve/reject
    ✦ Wallet recharge: POST /api/v1/wallet/recharge-request, GET /admin/wallet/pending-recharges
    ✦ PATCH /api/v1/wallet/recharge-requests/{id}/approve|reject
  
  frontend:
    ✦ LeadsWorkPage: add phone/email fields on create, show in list
    ✦ Call status dropdown on each lead row
    ✦ Payment proof upload modal (on leads page)
    ✦ Wallet recharge request form (UTR + optional file upload)
    ✦ Admin: recharge approval queue page

Sprint 2 (Week 3-4): FUNNEL
    ✦ Add day1_done, day2_done, d1_*/d2_* fields to Lead
    ✦ Create enrollment_links table
    ✦ Enrollment endpoint: POST /api/v1/leads/{id}/enrollment-link
    ✦ Public watch URL: GET /watch/{token} (no auth, sets watched_at)
    ✦ Day1 routing: PATCH /api/v1/leads/{id}/start-day1
    ✦ Day2 routing: PATCH /api/v1/leads/{id}/start-day2
    ✦ Batch checkboxes: PATCH /api/v1/leads/{id}/batch-done {slot: 'morning'}
    ✦ APScheduler: auto-expire job (every hour, check >24h in day1/day2/day3)

Sprint 3 (Week 5-6): TRAINING + REPORTING
    ✦ Create training_videos, training_progress, training_questions, training_test_attempts
    ✦ Training endpoints (CRUD for admin, watch progress for users, test submit)
    ✦ Create daily_reports table + endpoint
    ✦ Scoring service: calculate daily points per user
    ✦ Leaderboard endpoint: /api/v1/leaderboard

Sprint 4 (Week 7-8): ORG + GAMIFICATION
    ✦ Add upline_user_id, fbo_id to User model
    ✦ Registration approval flow (status: pending → approved)
    ✦ Org tree endpoint: /api/v1/org-tree
    ✦ Badges: create user_badges table + badge unlock triggers
    ✦ Points system: user.total_points updated on each scoring event
    ✦ Announcements table + endpoints
    ✦ Discipline engine service
```

---

## PART 12 — FRONTEND PAGES TO BUILD (in order)

```
Phase 1 — Shell → Functional:
  🔲 LeadsWorkPage — add phone/email, call status dropdown, payment proof upload button
  🔲 WorkboardPage — pull from Phase 2 (already partially improved)
  🔲 WalletPage — add recharge request form (UTR + screenshot)
  🔲 New: PaymentProofPage (leader) — list pending proofs, approve/reject with screenshot viewer
  🔲 New: WalletRechargePendingPage (admin) — approve/reject recharge requests
  🔲 AdminDashboardPage — KPI tiles (total leads, conversions, pipeline count, revenue)

Phase 2 — Funnel:
  🔲 LeadDetailPage — full lead view (timeline, call history, payment status, funnel progress)
  🔲 EnrollmentPage — generate video link, share via WhatsApp
  🔲 Day1ProgressPage — list of Day1 leads with batch checkboxes
  🔲 Day2ProgressPage — list of Day2 leads + MCQ test link generation
  🔲 New: PublicWatchPage (/watch/:token) — no-auth, video player, sets watched_at

Phase 3 — Training:
  🔲 TrainingPage — 7-day video series, unlock calendar
  🔲 TrainingTestPage — 30-question MCQ, submit, result, certificate
  🔲 DailyReportPage — daily form submission
  🔲 LeaderboardPage — points ranking, this week/month

Phase 4 — Admin Tools:
  🔲 OrgTreePage — hierarchy visual, assign upline
  🔲 UserApprovalsPage — pending registrations
  🔲 AdminSettingsPage — global config (pricing, limits, thresholds)
  🔲 AuditLogPage — full event log with filters
  🔲 AnnouncementsPage — admin post, team read
  🔲 StaleLeadsPage — at-risk leads + redistribution tool
```

---

## PART 13 — APPLE/PRODUCTION-GRADE UI RULES (ENFORCE ON ALL PAGES)

```
1. TYPOGRAPHY HIERARCHY (Inter variable font + system SF on Apple)
   Display (page hero):   font-size: 2rem,   font-weight: 700, letter-spacing: -0.03em
   Title (h1):            font-size: 1.25rem, font-weight: 600, letter-spacing: -0.022em
   Section (h2):          font-size: 1rem,    font-weight: 600, letter-spacing: -0.018em
   Body:                  font-size: 0.875rem, font-weight: 400, line-height: 1.55
   Caption/Label:         font-size: 0.75rem,  font-weight: 500, letter-spacing: 0.04em
   Micro:                 font-size: 0.65rem,  font-weight: 600 uppercase, letter-spacing: 0.08em

2. TOUCH TARGETS (iOS HIG compliance)
   Minimum: 44×44px for any tappable element
   Buttons: h-10 minimum (40px) on mobile, h-9 on desktop
   List rows: min-height: 52px on mobile
   Never put two tappable elements < 8px apart

3. SAFE AREA (iPhone notch / Dynamic Island)
   Header: padding-top: env(safe-area-inset-top)
   Bottom nav (if added): padding-bottom: env(safe-area-inset-bottom)

4. MOTION (reduced-motion respected)
   Transitions: 200ms ease-out for state changes
   Entrance: 150ms fade-in + 4px translate-y
   Loading: skeleton pulse, not spinner (less jarring)

5. FEEDBACK IMMEDIACY (feel like native)
   Optimistic updates: update UI before API confirms
   Button: active:scale-[0.97] + immediate state change
   Error: appear within 200ms of API error

6. EMPTY STATES (every list needs one)
   Not just text. Icon + headline + CTA button.
   Example: "No leads yet" + icon + "Add your first lead" button

7. LOADING STATES (every async section)
   Use Skeleton, not spinner
   Skeleton matches shape of actual content

8. ANDROID SPECIFICS
   ripple effect on buttons (add after-effect class)
   Bottom sheet instead of dropdown on mobile
   Font: Inter renders better than SF on Android

9. CONSISTENT DENSITY
   Desktop: lg:p-8 spacious
   Mobile: p-4 compact
   Never overflow horizontally — all tables scroll-x
```

---

## PART 14 — RISK ANALYSIS

```
Risk 1: WALLET DOUBLE-CREDIT ON RACE CONDITION
  Likelihood: Medium | Impact: Critical (financial)
  Mitigation: UNIQUE constraint on idempotency_key + SELECT FOR UPDATE on balance check
  Status: ⚠️ Needs implementation in Phase 1

Risk 2: LEAD STATE CORRUPTION
  Likelihood: High | Impact: High (data integrity)
  Current: No state machine — any status can be set to anything
  Mitigation: State machine service enforced at API layer BEFORE DB write
  Status: ⚠️ Needs implementation in Sprint 1

Risk 3: PAYMENT PROOF BYPASS
  Likelihood: Low-Medium | Impact: Critical (fraud)
  Mitigation: payment_done can only be set to true AFTER payment_approved_by is set
  Status: ⚠️ Needs implementation in Phase 1

Risk 4: POOL PRICING MANIPULATION
  Likelihood: Low | Impact: Medium
  Mitigation: pool_price is set once by admin, IMMUTABLE after claim (snapshot)
  Status: Design-level fix in Phase 1

Risk 5: SCHEDULER RACE (multiple instances auto-expire same lead twice)
  Likelihood: Medium (when Render scales) | Impact: Medium
  Mitigation: Distributed lock (Redis) or single-instance scheduler enforcement
  Status: Low priority until scale > 1 instance

Risk 6: FILE UPLOAD ABUSE (large screenshots)
  Likelihood: High | Impact: Medium (storage cost)
  Mitigation: Max 5MB, accept JPEG/PNG/WebP only, compress on upload
  Status: ⚠️ Implement in Phase 1 upload endpoint

Risk 7: INACTIVE USER DATA EXPOSURE
  Likelihood: Low | Impact: Critical (privacy)
  Mitigation: All queries MUST use apply_lead_scope / apply_user_scope middleware
  Status: ⚠️ CRITICAL — implement scope middleware Sprint 1

Risk 8: STALE LEAD AUTO-REASSIGN VIOLATES OWNERSHIP
  Likelihood: Medium | Impact: Medium
  Mitigation: Admin-only redistribution, audit log on every reassign
  Status: Phase 4, audit log from Sprint 1

Risk 9: FBO ID CIRCULAR UPLINE
  Likelihood: Low (known issue in old app) | Impact: High (infinite loop)
  Mitigation: Validate: new upline's upline chain does not include the user
  Status: Phase 4 org tree
```

---

## PART 15 — MINIMAL VIABLE PRODUCTION (MVP)

What needs to be DONE before the app can replace the old one for even 10 users:

```
✅ Already done:
- Auth (login, logout, JWT cookies)
- Basic lead CRUD with archive/restore/delete
- Basic workboard
- Basic wallet ledger
- Basic lead pool
- Follow-ups
- WebSocket realtime
- CI/CD + auto-deploy
- Design system

❌ Must do before any real user touches this:
1. Add phone + email to Lead (without this, useless for calling)
2. Call status dropdown per lead (the primary team workflow)
3. State machine enforcement (prevent data corruption)
4. Role-based data scoping at SQL level (security critical)
5. Payment proof upload + approval (the ₹196 gate — entire funnel depends on this)
6. Wallet recharge request (how teams load their wallet)
7. Admin dashboard with basic KPIs (otherwise admin is blind)
8. LeadDetailPage (need to see a lead's full history, calls, timeline)

Timeline: 2-3 weeks of focused development with 1 fullstack developer.
```

---

*Document generated by Senior System Architect. Update as each phase completes.*
*Next review: After Sprint 1 completion.*
