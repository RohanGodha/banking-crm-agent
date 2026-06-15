-- ===========================================================================
-- banking-crm-agent — SQLite schema
-- Same logical shape as the Databricks Delta tables.
-- ===========================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    age                 INTEGER NOT NULL,
    city                TEXT NOT NULL,
    segment             TEXT NOT NULL,            -- mass | mass_affluent | affluent | hnw
    employment          TEXT NOT NULL,            -- salaried | self_employed | business
    monthly_income      REAL NOT NULL,
    account_open_date   TEXT NOT NULL,            -- ISO date
    kyc_status          TEXT NOT NULL DEFAULT 'verified',
    phone               TEXT NOT NULL,
    email               TEXT,
    risk_appetite       TEXT NOT NULL DEFAULT 'medium',
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_customers_city    ON customers(city);
CREATE INDEX IF NOT EXISTS idx_customers_segment ON customers(segment);

CREATE TABLE IF NOT EXISTS accounts (
    id                  TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(id),
    type                TEXT NOT NULL,            -- savings | current | salary
    balance             REAL NOT NULL,
    avg_balance_6m      REAL NOT NULL,
    opened_at           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts(customer_id);

CREATE TABLE IF NOT EXISTS transactions (
    id                  TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(id),
    ts                  TEXT NOT NULL,
    amount              REAL NOT NULL,            -- positive = credit, negative = debit
    category            TEXT NOT NULL,            -- salary | upi | emi | travel | shopping | utility | investment | other
    channel             TEXT NOT NULL,            -- upi | neft | card | atm | branch
    merchant            TEXT
);

CREATE INDEX IF NOT EXISTS idx_txn_customer_ts ON transactions(customer_id, ts);
CREATE INDEX IF NOT EXISTS idx_txn_category    ON transactions(category);

CREATE TABLE IF NOT EXISTS products (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    category            TEXT NOT NULL,            -- loan | card | investment | overdraft
    interest_rate       REAL,
    min_income          REAL,
    min_age             INTEGER,
    max_age             INTEGER,
    description         TEXT,
    eligibility_json    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS holdings (
    customer_id         TEXT NOT NULL REFERENCES customers(id),
    product_id          TEXT NOT NULL REFERENCES products(id),
    opened_at           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active',
    PRIMARY KEY (customer_id, product_id)
);

CREATE TABLE IF NOT EXISTS interactions (
    id                  TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(id),
    ts                  TEXT NOT NULL,
    channel             TEXT NOT NULL,            -- call | whatsapp | email | branch
    summary             TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_interactions_customer ON interactions(customer_id);

-- --- Runtime tables (always SQLite, never Databricks) ---

CREATE TABLE IF NOT EXISTS sessions (
    id                  TEXT PRIMARY KEY,
    rm_id               TEXT NOT NULL DEFAULT 'rohan',
    title               TEXT,
    state_json          TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id                  TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role                TEXT NOT NULL,            -- user | assistant | system
    content             TEXT NOT NULL,
    payload_json        TEXT,
    ts                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, ts);

CREATE TABLE IF NOT EXISTS agent_traces (
    id                  TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    node                TEXT NOT NULL,
    input_json          TEXT,
    output_json         TEXT,
    llm_route           TEXT,
    source              TEXT,
    latency_ms          INTEGER,
    ts                  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_traces_session ON agent_traces(session_id, ts);

CREATE TABLE IF NOT EXISTS outreach_drafts (
    id                  TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    customer_id         TEXT NOT NULL REFERENCES customers(id),
    product_id          TEXT NOT NULL REFERENCES products(id),
    channel             TEXT NOT NULL DEFAULT 'whatsapp',
    message             TEXT NOT NULL,
    score               REAL,
    rationale_json      TEXT,
    compliance_json     TEXT,
    status              TEXT NOT NULL DEFAULT 'draft',   -- draft | approved | sent | rejected
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_drafts_session ON outreach_drafts(session_id);

CREATE TABLE IF NOT EXISTS tool_cache (
    cache_key           TEXT PRIMARY KEY,
    payload_json        TEXT NOT NULL,
    created_at          INTEGER NOT NULL          -- unix seconds
);
