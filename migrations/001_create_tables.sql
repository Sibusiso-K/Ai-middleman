-- Contacts table
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    contact_id VARCHAR(50) UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(255),
    company VARCHAR(255),
    title VARCHAR(255),
    sector VARCHAR(255),
    specialty VARCHAR(255),
    location VARCHAR(255),
    seniority VARCHAR(255),
    expertise_tags TEXT,
    can_help_with TEXT,
    looking_for TEXT,
    relationship_strength INTEGER,
    how_alex_knows_them TEXT,
    is_vip BOOLEAN,
    last_contacted DATE,
    intros_made INTEGER,
    deals_closed INTEGER,
    preferred_contact_channel VARCHAR(50),
    do_not_intro_to TEXT,
    last_verified DATE,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    sender_number VARCHAR(20) NOT NULL,
    message_text TEXT NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

-- Match history table
CREATE TABLE IF NOT EXISTS match_history (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id),
    contact_id INTEGER REFERENCES contacts(id),
    rank_position INTEGER NOT NULL,
    confidence FLOAT NOT NULL,
    reasoning TEXT,
    feedback VARCHAR(20),  -- 'accepted', 'rejected', 'pending'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_contacts_fullname ON contacts(full_name);
CREATE INDEX IF NOT EXISTS idx_contacts_title ON contacts(title);
CREATE INDEX IF NOT EXISTS idx_contacts_sector ON contacts(sector);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_number);
