CREATE DATABASE virtual_pet_testing;

\c virtual_pet_testing;


-- django will take care of this, but i am still keeping the sql for reference
/*
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(80),
    password_hash VARCHAR(255) NOT NULL,
    password_salt VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_staff BOOLEAN NOT NULL DEFAULT FALSE,
    is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

INSERT INTO roles (name) VALUES ('User'), ('Moderator'), ('Admin');

CREATE TABLE user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE pets (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(60) NOT NULL,
    visibility VARCHAR(20) NOT NULL DEFAULT 'private',
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_interaction_at TIMESTAMP
);

-- this is for if we go with llm api
CREATE TABLE pet_personalities (
    id SERIAL PRIMARY KEY,
    pet_id INTEGER UNIQUE NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    roleplay_prompt TEXT NOT NULL,
    traits JSONB NOT NULL DEFAULT '{}'::jsonb,
    tone VARCHAR(40),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pet_assets (
    id SERIAL PRIMARY KEY,
    pet_id INTEGER NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    original_image_url TEXT NOT NULL,
    cutout_image_url TEXT,
    model_3d_url TEXT,
    asset_type VARCHAR(20) NOT NULL DEFAULT 'image',
    generator VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- to be determined
CREATE TABLE pet_stats (
    id SERIAL PRIMARY KEY,
    pet_id INTEGER UNIQUE NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    hunger INTEGER NOT NULL DEFAULT 50 CHECK (hunger BETWEEN 0 AND 100),
    energy INTEGER NOT NULL DEFAULT 50 CHECK (energy BETWEEN 0 AND 100),
    happiness INTEGER NOT NULL DEFAULT 50 CHECK (happiness BETWEEN 0 AND 100),
    cleanliness INTEGER NOT NULL DEFAULT 50 CHECK (cleanliness BETWEEN 0 AND 100),
    health INTEGER NOT NULL DEFAULT 100 CHECK (health BETWEEN 0 AND 100),
    level INTEGER NOT NULL DEFAULT 1 CHECK (level >= 1),
    experience INTEGER NOT NULL DEFAULT 0 CHECK (experience >= 0),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE pet_action_log (
    id SERIAL PRIMARY KEY,
    pet_id INTEGER NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR(30) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,
    pet_id INTEGER NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model VARCHAR(80),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP
);

CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sender VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    tokens_in INTEGER,
    tokens_out INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- these are for if we go with uploading pets/sharing them
CREATE TABLE user_pet_follows (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pet_id INTEGER NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, pet_id)
);

CREATE TABLE pet_likes (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pet_id INTEGER NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, pet_id)
);

CREATE TABLE moderation_reports (
    id SERIAL PRIMARY KEY,
    reporter_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    pet_id INTEGER REFERENCES pets(id) ON DELETE CASCADE,
    asset_id INTEGER REFERENCES pet_assets(id) ON DELETE CASCADE,
    reason VARCHAR(80) NOT NULL,
    details TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE TABLE content_scans (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES pet_assets(id) ON DELETE CASCADE,
    provider VARCHAR(60) NOT NULL,
    verdict VARCHAR(30) NOT NULL,
    score NUMERIC(6,5),
    raw JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE auth_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    user_agent VARCHAR(255),
    ip_address VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP
);

CREATE INDEX idx_pets_owner_id ON pets(owner_id);
CREATE INDEX idx_pets_visibility ON pets(visibility);
CREATE INDEX idx_pet_assets_pet_id ON pet_assets(pet_id);
CREATE INDEX idx_pet_action_log_pet_id_created_at ON pet_action_log(pet_id, created_at);
CREATE INDEX idx_chat_sessions_pet_id ON chat_sessions(pet_id);
CREATE INDEX idx_chat_messages_session_id_created_at ON chat_messages(session_id, created_at);
CREATE INDEX idx_content_scans_asset_id_created_at ON content_scans(asset_id, created_at);
CREATE INDEX idx_moderation_reports_status_created_at ON moderation_reports(status, created_at);
CREATE INDEX idx_auth_sessions_user_id_expires_at ON auth_sessions(user_id, expires_at);
*/