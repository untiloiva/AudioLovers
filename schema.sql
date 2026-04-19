CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE songs (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT,
    genre TEXT NOT NULL,
    filename TEXT NOT NULL,
    user TEXT NOT NULL
);

CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    song_id INTEGER,
    user TEXT NOT NULL,
    created DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(song_id) REFERENCES songs(id) ON DELETE CASCADE
);
