CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    region VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS calculations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    car_data JSONB NOT NULL,
    market_data JSONB NOT NULL,
    repair_estimate JSONB NOT NULL,
    scores JSONB NOT NULL,
    final_report TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_cache (
    id SERIAL PRIMARY KEY,
    prompt_hash VARCHAR(64) UNIQUE NOT NULL,
    response JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ai_cache_expiry_idx ON ai_cache(expires_at);

