CREATE TABLE IF NOT EXISTS guilds (
    guild_id BIGINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    guild_id BIGINT REFERENCES guilds ON DELETE CASCADE,
    user_id BIGINT,
    cash BIGINT DEFAULT 0,
    vault BIGINT DEFAULT 500,
    pet_name VARCHAR DEFAULT 'happy shiba',
    xp BIGINT DEFAULT 0,
    level BIGINT DEFAULT 1
)
