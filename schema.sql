CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE songs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    genre TEXT NOT NULL,
    filename TEXT NOT NULL,
    user TEXT NOT NULL
);
