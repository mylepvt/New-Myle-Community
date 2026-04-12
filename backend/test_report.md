# Myle Dashboard Test Report

Generated: 1.349005375

## Phase 1: Training System

**Status:** FAILED

### Output:

```
Starting training system tests...
==================================================
Testing training surface service...
  Videos: 0
  Progress: 0
  Note: Training catalog is empty - admin can seed `training_videos`.
  Unlock dates: {}
  Training surface test: FAILED - Expected 7 videos, got 0

Testing calendar enforcement...
  Calendar enforcement test: FAILED - an integer is required (got type str)

Testing training progress...
  Training progress test: FAILED - an integer is required (got type str)

==================================================
Results: 0 passed, 3 failed
Some tests FAILED. Check the output above.

```

## Phase 2: Lead Pipeline

**Status:** FAILED

### Output:

```
Starting pipeline system tests...
==================================================
Testing pipeline service...
  Pipeline columns: 13
  Total leads: 0
  User role: admin
  Pipeline service test: PASSED

Testing status transitions...
  Status transitions test: PASSED

Testing role permissions...
  Role permissions test: FAILED - (sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class 'asyncpg.exceptions.ForeignKeyViolationError'>: insert or update on table "leads" violates foreign key constraint "leads_assigned_to_user_id_fkey"
DETAIL:  Key (assigned_to_user_id)=(2) is not present in table "users".
[SQL: INSERT INTO leads (name, status, created_by_user_id, archived_at, deleted_at, in_pool, pool_price_cents, phone, email, city, source, notes, assigned_to_user_id, call_status, call_count, last_called_at, whatsapp_sent_at, payment_status, payment_amount_cents, payment_proof_url, payment_proof_uploaded_at, day1_completed_at, day2_completed_at, day3_completed_at, d1_morning, d1_afternoon, d1_evening, d2_morning, d2_afternoon, d2_evening, no_response_attempt_count) VALUES ($1::VARCHAR, $2::VARCHAR, $3::INTEGER, $4::TIMESTAMP WITH TIME ZONE, $5::TIMESTAMP WITH TIME ZONE, $6::BOOLEAN, $7::INTEGER, $8::VARCHAR, $9::VARCHAR, $10::VARCHAR, $11::VARCHAR, $12::VARCHAR, $13::INTEGER, $14::VARCHAR, $15::INTEGER, $16::TIMESTAMP WITH TIME ZONE, $17::TIMESTAMP WITH TIME ZONE, $18::VARCHAR, $19::INTEGER, $20::VARCHAR, $21::TIMESTAMP WITH TIME ZONE, $22::TIMESTAMP WITH TIME ZONE, $23::TIMESTAMP WITH TIME ZONE, $24::TIMESTAMP WITH TIME ZONE, $25::BOOLEAN, $26::BOOLEAN, $27::BOOLEAN, $28::BOOLEAN, $29::BOOLEAN, $30::BOOLEAN, $31::INTEGER) RETURNING leads.id, leads.created_at]
[parameters: ('Permission Test Lead', 'new_lead', 1, None, None, False, None, '0987654321', 'permission@example.com', None, None, None, 2, 'not_called', 0, None, None, None, None, None, None, None, None, None, False, False, False, False, False, False, 0)]
(Background on this error at: https://sqlalche.me/e/20/gkpj)

Testing auto-expiry...
  Auto-expiry test: FAILED - name 'timedelta' is not defined

Testing pipeline metrics...
  Pipeline metrics test: PASSED

Testing business rules...
  Business rules test: FAILED - Valid transition failed: Must be paid before day1

==================================================
Results: 3 passed, 3 failed
Some tests FAILED. Check the output above.

```

## Phase 3: Wallet System

**Status:** FAILED

### Output:

```
Starting wallet system tests...
==================================================
Testing wallet balance calculation...
  Initial balance: 0 INR
  Wallet balance calculation: PASSED

Testing lead claim affordability...
  Lead claim affordability: PASSED

Testing wallet deduction...
  Wallet deduction: FAILED - Expected -10000, got 0

Testing wallet summary...
  Wallet summary: PASSED

Testing manual adjustment...
  Manual adjustment: PASSED

Testing transaction validation...
  Transaction validation: PASSED

Testing admin overview...
  Admin overview: PASSED

==================================================
Results: 6 passed, 1 failed
Some tests FAILED. Check the output above.

```

## Phase 4: Analytics System

**Status:** FAILED

### Output:

```
Starting analytics system tests...
==================================================
Testing team performance summary...
  Team performance summary: FAILED - __init__() got an unexpected keyword argument 'else_'

Testing individual performance...
  Individual performance: FAILED - __init__() got an unexpected keyword argument 'else_'

Testing leaderboard...
  Leaderboard: PASSED

Testing system overview...
  System overview: FAILED - __init__() got an unexpected keyword argument 'else_'

Testing daily trends...
  Daily trends: PASSED

Testing data consistency...
  Data consistency: FAILED - __init__() got an unexpected keyword argument 'else_'

Testing period variations...
  Period variations: FAILED - __init__() got an unexpected keyword argument 'else_'

==================================================
Results: 2 passed, 5 failed
Some tests FAILED. Check the output above.

```

## Phase 5: Settings System

**Status:** FAILED

### Output:

```
Starting settings system tests...
==================================================
Testing app settings CRUD...
  App settings CRUD: PASSED

Testing user profile management...
  User profile management: PASSED

Testing user preferences...
  User preferences: PASSED

Testing system configuration...
  System configuration: PASSED

Testing system users summary...
  System users summary: FAILED - name 'func' is not defined

Testing user hierarchy validation...
  User hierarchy validation: PASSED

Testing audit log...
  Audit log: PASSED

Testing settings validation...
  Settings validation: PASSED

==================================================
Results: 7 passed, 1 failed
Some tests FAILED. Check the output above.

```

