import os
import sqlite3
import secrets

from flask import (
    Flask, redirect, render_template, request,
    session, flash, abort, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash

import config
import db


app = Flask(__name__)
app.secret_key = config.secret_key
app.config["UPLOAD_FOLDER"] = "uploads"

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

avatars_path = os.path.join(app.config["UPLOAD_FOLDER"], "avatars")
covers_path = os.path.join(app.config["UPLOAD_FOLDER"], "covers")
os.makedirs(avatars_path, exist_ok=True)
os.makedirs(covers_path, exist_ok=True)

GENRES = [
    "Pop", "Rock", "Hip-Hop", "R&B", "Jazz", "Classical",
    "Electronic", "Metal", "Country", "Folk", "Reggae",
    "Blues", "Punk", "Indie", "Latin", "Other"
]


# ---------- Helpers ----------

def allowed_image(filename):
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def check_csrf():
    if request.form.get("csrf_token") != session.get("csrf_token"):
        abort(403)


@app.before_request
def set_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)


# ---------- Routes ----------

@app.route("/")
def index():
    sql = """
        SELECT id, title, artist, genre, filename, user, cover_image
        FROM songs
    """
    songs = db.query(sql)
    return render_template("index.html", songs=songs)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/new_item")
def new_item():
    if "username" not in session:
        return redirect("/login")
    return render_template("new_item.html", genres=GENRES)


@app.route("/create_item", methods=["POST"])
def create_item():
    if "username" not in session:
        return redirect("/login")
    check_csrf()

    title = request.form["title"].strip()
    artist = request.form.get("artist", "").strip()
    genre = request.form["genre"].strip()

    if not title:
        flash("Title cannot be empty.", "error")
        return redirect("/new_item")
    if not genre:
        flash("Genre cannot be empty.", "error")
        return redirect("/new_item")

    file = request.files["file"]
    if not file or not file.filename.lower().endswith(".mp3"):
        flash("File must be in MP3 format.", "error")
        return redirect("/new_item")

    sql = """
        INSERT INTO songs (title, artist, genre, filename, cover_image, user)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    db.execute(sql, [title, artist, genre, "_tmp", None, session["username"]])
    song_id = db.last_insert_id()

    filename = f"{song_id}.mp3"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    cover_filename = None
    cover_file = request.files.get("cover_image")
    if cover_file and cover_file.filename and allowed_image(cover_file.filename):
        ext = cover_file.filename.rsplit(".", 1)[1].lower()
        cover_filename = f"{song_id}.{ext}"
        cover_file.save(os.path.join(covers_path, cover_filename))

    db.execute(
        "UPDATE songs SET filename = ?, cover_image = ? WHERE id = ?",
        [filename, cover_filename, song_id],
    )

    flash("Audio added successfully!", "success")
    return redirect("/")


@app.route("/edit_song/<int:song_id>")
def edit_song(song_id):
    if "username" not in session:
        return redirect("/login")

    song = db.query(
        "SELECT id, title, artist, genre, cover_image, user FROM songs WHERE id = ?",
        [song_id],
    )
    if not song:
        abort(404)
    if song[0]["user"] != session["username"]:
        flash("Not authorized to edit this.", "error")
        return redirect("/")

    return render_template("edit_song.html", song=song[0], genres=GENRES)


@app.route("/update_song", methods=["POST"])
def update_song():
    if "username" not in session:
        return redirect("/login")
    check_csrf()

    song_id = request.form["song_id"]
    title = request.form["title"].strip()
    artist = request.form.get("artist", "").strip()
    genre = request.form["genre"].strip()

    if not title or not genre:
        flash("Title and genre are required.", "error")
        return redirect(f"/edit_song/{song_id}")

    song = db.query("SELECT user, cover_image FROM songs WHERE id = ?", [song_id])
    if not song or song[0]["user"] != session["username"]:
        abort(403)

    cover_filename = song[0]["cover_image"]
    cover_file = request.files.get("cover_image")
    if cover_file and cover_file.filename and allowed_image(cover_file.filename):
        if cover_filename:
            old = os.path.join(covers_path, cover_filename)
            if os.path.exists(old):
                os.remove(old)

        ext = cover_file.filename.rsplit(".", 1)[1].lower()
        cover_filename = f"{song_id}.{ext}"
        cover_file.save(os.path.join(covers_path, cover_filename))

    db.execute(
        """
        UPDATE songs
        SET title = ?, artist = ?, genre = ?, cover_image = ?
        WHERE id = ?
        """,
        [title, artist, genre, cover_filename, song_id],
    )

    flash("Audio updated successfully!", "success")
    return redirect(f"/song/{song_id}")


@app.route("/delete_song", methods=["POST"])
def delete_song():
    if "username" not in session:
        return redirect("/login")
    check_csrf()

    song_id = request.form["song_id"]
    song = db.query(
        "SELECT filename, cover_image, user FROM songs WHERE id = ?", [song_id]
    )

    if not song or song[0]["user"] != session["username"]:
        flash("Not authorized.", "error")
        return redirect("/")

    filename = song[0]["filename"]
    cover = song[0]["cover_image"]

    db.execute("DELETE FROM songs WHERE id = ?", [song_id])

    if not db.query("SELECT 1 FROM songs WHERE filename = ?", [filename]):
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(path):
            os.remove(path)

    if cover:
        cover_path = os.path.join(covers_path, cover)
        if os.path.exists(cover_path):
            os.remove(cover_path)

    flash("Audio deleted.", "success")
    return redirect("/")


@app.route("/edit_profile")
def edit_profile():
    if "username" not in session:
        return redirect("/login")

    user = db.query(
        "SELECT username, avatar, bio FROM users WHERE username = ?",
        [session["username"]],
    )
    if not user:
        abort(404)
    return render_template("edit_profile.html", user=user[0])


@app.route("/update_profile", methods=["POST"])
def update_profile():
    if "username" not in session:
        return redirect("/login")
    check_csrf()

    bio = request.form.get("bio", "").strip()
    avatar = db.query(
        "SELECT avatar FROM users WHERE username = ?", [session["username"]]
    )[0]["avatar"]

    file = request.files.get("avatar")
    if file and file.filename and allowed_image(file.filename):
        if avatar:
            old = os.path.join(avatars_path, avatar)
            if os.path.exists(old):
                os.remove(old)

        ext = file.filename.rsplit(".", 1)[1].lower()
        avatar = f"{session['username']}.{ext}"
        file.save(os.path.join(avatars_path, avatar))

    db.execute(
        "UPDATE users SET avatar = ?, bio = ? WHERE username = ?",
        [avatar, bio, session["username"]],
    )

    flash("Profile updated!", "success")
    return redirect(f"/user/{session['username']}")


@app.route("/register")
def register():
    return render_template("register.html")


@app.route("/create", methods=["POST"])
def create():
    check_csrf()

    username = request.form["username"].strip()
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    if not username or " " in username:
        flash("Invalid username.", "error")
        return redirect("/register")
    if password1 != password2:
        flash("Passwords do not match.", "error")
        return redirect("/register")
    if len(password1) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect("/register")
    if not any(c.islower() for c in password1):
        flash("Password must contain a lowercase letter.", "error")
        return redirect("/register")
    if not any(c.isupper() for c in password1):
        flash("Password must contain an uppercase letter.", "error")
        return redirect("/register")
    if not any(c.isdigit() for c in password1):
        flash("Password must contain a number.", "error")
        return redirect("/register")
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password1):
        flash("Password must contain a special character.", "error")
        return redirect("/register")

    try:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            [username, generate_password_hash(password1)],
        )
    except sqlite3.IntegrityError:
        flash("Username already taken.", "error")
        return redirect("/register")

    session["username"] = username
    flash(f"Welcome, {username}!", "success")
    return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    check_csrf()
    username = request.form["username"]
    password = request.form["password"]

    user = db.query(
        "SELECT password_hash FROM users WHERE username = ?", [username]
    )
    if not user or not check_password_hash(user[0][0], password):
        flash("Wrong username or password.", "error")
        return redirect("/login")

    session["username"] = username
    flash(f"Welcome back, {username}!", "success")
    return redirect("/")


@app.route("/search")
def search():
    q = request.args.get("query", "")
    like = f"%{q}%"
    songs = db.query(
        """
        SELECT id, title, artist, genre, filename, user, cover_image
        FROM songs
        WHERE title LIKE ? OR genre LIKE ? OR artist LIKE ? OR user LIKE ?
        """,
        [like, like, like, like],
    )
    return render_template("index.html", songs=songs, search_query=q)


@app.route("/song/<int:song_id>")
def song_page(song_id):
    song = db.query(
        "SELECT id, title, artist, genre, filename, user, cover_image FROM songs WHERE id = ?",
        [song_id],
    )
    if not song:
        abort(404)

    comments = db.query(
        """
        SELECT id, content, created, user
        FROM comments
        WHERE song_id = ?
        ORDER BY created ASC
        """,
        [song_id],
    )

    return render_template("song.html", song=song[0], comments=comments)


@app.route("/add_comment", methods=["POST"])
def add_comment():
    if "username" not in session:
        return redirect("/login")
    check_csrf()

    content = request.form["content"].strip()
    song_id = request.form["song_id"]

    if not content:
        flash("Comment cannot be empty.", "error")
        return redirect(f"/song/{song_id}")

    db.execute(
        "INSERT INTO comments (content, song_id, user) VALUES (?, ?, ?)",
        [content, song_id, session["username"]],
    )

    return redirect(f"/song/{song_id}")


@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect("/login")
    return redirect(f"/user/{session['username']}")


@app.route("/user/<username>")
def user_profile(username):
    user = db.query(
        "SELECT avatar, bio FROM users WHERE username = ?", [username]
    )
    if not user:
        abort(404)

    songs = db.query(
        "SELECT * FROM songs WHERE user = ?", [username]
    )

    comments = db.query(
        """
        SELECT c.id, c.content, c.created, s.title AS song_title, c.song_id, c.user
        FROM comments c
        JOIN songs s ON c.song_id = s.id
        WHERE c.user = ?
        ORDER BY c.created DESC
        LIMIT 50
        """,
        [username],
    )

    return render_template(
        "profile.html",
        profile_user=username,
        avatar=user[0]["avatar"],
        bio=user[0]["bio"],
        songs=songs,
        comments=comments,
    )


@app.route("/delete_comment", methods=["POST"])
def delete_comment():
    if "username" not in session:
        return redirect("/login")
    check_csrf()

    cid = request.form["comment_id"]
    song_id = request.form.get("song_id", "")

    owner = db.query("SELECT user FROM comments WHERE id = ?", [cid])
    if owner and owner[0][0] == session["username"]:
        db.execute("DELETE FROM comments WHERE id = ?", [cid])
        flash("Comment deleted.", "success")

    return redirect(f"/song/{song_id}" if song_id else "/")


@app.route("/logout")
def logout():
    session.pop("username", None)
    flash("You have been logged out.", "success")
    return redirect("/")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("404.html"), 403