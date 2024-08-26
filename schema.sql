CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT UNIQUE,
    username TEXT,
    avatar_url TEXT
);

CREATE TABLE memes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    meme_url TEXT,
    likes INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    meme_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(meme_id) REFERENCES memes(id)
);

CREATE TABLE badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    badge_name TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
