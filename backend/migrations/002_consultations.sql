BEGIN;
CREATE TABLE IF NOT EXISTS accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username text UNIQUE NOT NULL,
    password_hash text NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    digest text PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES accounts ON DELETE CASCADE,
    expires_at timestamptz NOT NULL DEFAULT now() + interval '7 days'
);
CREATE TABLE IF NOT EXISTS consultations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id uuid NOT NULL REFERENCES accounts ON DELETE CASCADE,
    question text NOT NULL,
    answer jsonb NOT NULL,
    helpful boolean,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS consultations_owner_idx ON consultations(account_id, created_at DESC);
COMMIT;
