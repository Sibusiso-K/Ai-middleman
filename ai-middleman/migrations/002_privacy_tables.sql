-- Privacy layer tables for AI Middleman
-- introduction_requests: logs when a WhatsApp user selects a contact for introduction
-- conversation_state: remembers the last matches shown to each user

CREATE TABLE IF NOT EXISTS introduction_requests (
    id SERIAL PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id),
    requester_number VARCHAR(20) NOT NULL,
    contact_id INTEGER REFERENCES contacts(id),
    status VARCHAR(20) DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    approved_by VARCHAR(100),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_intro_requests_status ON introduction_requests(status);
CREATE INDEX IF NOT EXISTS idx_intro_requests_requester ON introduction_requests(requester_number);