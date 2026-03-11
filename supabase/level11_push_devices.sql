CREATE TABLE IF NOT EXISTS push_devices (
    id TEXT PRIMARY KEY,
    token TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    platform TEXT DEFAULT 'expo',
    label TEXT,
    active BOOLEAN DEFAULT true,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_push_devices_token_hash
    ON push_devices(token_hash);

CREATE INDEX IF NOT EXISTS idx_push_devices_active
    ON push_devices(active);
