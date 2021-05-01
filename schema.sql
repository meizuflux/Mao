CREATE TABLE IF NOT EXISTS guilds (
    guild_id BIGINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id BIGINT PRIMARY KEY REFERENCES guilds ON DELETE CASCADE,
    leveling BOOLEAN DEFAULT True,
    welcoming BOOLEAN DEFAULT False
);

CREATE TABLE IF NOT EXISTS users (
    guild_id BIGINT REFERENCES guilds ON DELETE CASCADE,
    user_id BIGINT,
    cash BIGINT DEFAULT 0,
    vault BIGINT DEFAULT 500,
    pet_name VARCHAR DEFAULT 'happy shiba',
    xp BIGINT DEFAULT 0,
    level BIGINT DEFAULT 1,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS cooldowns (
    guild_id BIGINT REFERENCES guilds ON DELETE CASCADE DEFAULT NULL,
    user_id BIGINT,
    command TEXT,
    expires DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS welcome (
    guild_id BIGINT PRIMARY KEY REFERENCES guilds ON DELETE CASCADE NOT NULL,
    embed BOOLEAN DEFAULT False,
    dm BOOLEAN DEFAULT False,
    channel_id BIGINT,
    role_id BIGINT,
    message VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS errors (
    id SERIAL PRIMARY KEY,
    error VARCHAR NOT NULL,
    traceback VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    function VARCHAR NOT NULL,
    occurrences BIGINT NOT NULL DEFAULT 1,
    occurred_at TIMESTAMP NOT NULL DEFAULT timezone('UTC'::text, now()),
    handled BOOLEAN NOT NULL DEFAULT False,
    frames JSONB NOT NULL,
    context JSONB[] NOT NULL
)
