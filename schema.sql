-- AW Client Report Portal — SQLite schema.
-- Run via db.init_db() on first boot. Idempotent: safe to run repeatedly.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name          TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clients (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Client 1 (always present)
    c1_name           TEXT NOT NULL,
    c1_dob            TEXT,
    c1_ssn_last4      TEXT,
    c1_monthly_salary REAL NOT NULL DEFAULT 0,
    -- Client 2 (spouse, optional)
    c2_name           TEXT,
    c2_dob            TEXT,
    c2_ssn_last4      TEXT,
    c2_monthly_salary REAL NOT NULL DEFAULT 0,
    -- SACS budget (static)
    monthly_outflow   REAL NOT NULL DEFAULT 0,
    floor             REAL NOT NULL DEFAULT 1000,
    ded_auto          REAL NOT NULL DEFAULT 0,
    ded_home          REAL NOT NULL DEFAULT 0,
    ded_health        REAL NOT NULL DEFAULT 0,
    -- Trust
    trust_address     TEXT,
    -- Audit
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Variable-count list of accounts per client.
-- kind: 'c1_retirement' | 'c2_retirement' | 'non_retirement'
-- is_sacs (for non-retirement only): 'inflow' | 'outflow' | 'private_reserve' | NULL
CREATE TABLE IF NOT EXISTS accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER NOT NULL,
    kind        TEXT NOT NULL CHECK(kind IN ('c1_retirement','c2_retirement','non_retirement')),
    type        TEXT NOT NULL,
    last4       TEXT,
    is_sacs     TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS liabilities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id     INTEGER NOT NULL,
    type          TEXT NOT NULL,
    interest_rate REAL NOT NULL DEFAULT 0,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

-- Snapshot of every generated report for history/audit.
CREATE TABLE IF NOT EXISTS reports (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id      INTEGER NOT NULL,
    generated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    generated_by   INTEGER,                   -- user id
    balances_json  TEXT NOT NULL,             -- the raw inputs
    computed_json  TEXT NOT NULL,             -- the derived totals
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (generated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_accounts_client    ON accounts(client_id, kind, sort_order);
CREATE INDEX IF NOT EXISTS idx_liabilities_client ON liabilities(client_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_reports_client     ON reports(client_id, generated_at DESC);
