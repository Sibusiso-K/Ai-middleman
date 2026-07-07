-- Audit trail for contact information updates submitted conversationally
-- via WhatsApp. The contacts table stays as-is (so Stage 1 keyword matching
-- keeps working with no query changes); updates go directly into contacts and
-- every change is logged here with before/after values, who said it, and the
-- raw WhatsApp message that triggered it.

CREATE TABLE IF NOT EXISTS contact_change_log (
    id              SERIAL PRIMARY KEY,
    contact_id      INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    attribute_name  VARCHAR(100) NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    changed_by      VARCHAR(100) NOT NULL DEFAULT 'Sam',  -- 'Sam', 'Alex', 'system'
    source_message  TEXT,          -- the WhatsApp text that triggered the update
    changed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_change_log_contact
    ON contact_change_log(contact_id, changed_at DESC);

-- Sam Ndlovu: the friend who uses this system in demos. Seeded here so
-- the self-update flow ("I moved to Yoco") resolves to a real contact record.
-- contact_id 'sam-ndlovu' is used by update_extractor.py to detect first-person
-- updates — FRIEND_CONTACT_ID env var overrides it if you rename Sam.
INSERT INTO contacts (
    contact_id,
    full_name,
    phone,
    email,
    company,
    title,
    sector,
    specialty,
    location,
    seniority,
    expertise_tags,
    can_help_with,
    looking_for,
    relationship_strength,
    how_alex_knows_them,
    is_vip,
    last_verified,
    comment
) VALUES (
    'sam-ndlovu',
    'Sam Ndlovu',
    '27820001234',
    'sam.ndlovu@takealot.com',
    'Takealot',
    'Senior Software Engineer',
    'Tech',
    'E-commerce, Backend Engineering',
    'Cape Town, South Africa',
    'Mid',
    'Python, FastAPI, PostgreSQL, distributed systems, e-commerce',
    'Backend engineering advice, South African tech landscape, hiring referrals',
    'Seed-stage startup opportunities, VC introductions in fintech',
    5,
    'University friend — Wits CS class of 2019',
    FALSE,
    CURRENT_DATE,
    'Demo contact — updates his own record via WhatsApp to demonstrate the self-update flow'
) ON CONFLICT (contact_id) DO NOTHING;
