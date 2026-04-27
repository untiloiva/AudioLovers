import os
import sqlite3
from flask import Flask
from flask import redirect, render_template, request, session, flash, abort
from flask import send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import config
import db

app = Flask(__name__)
app.secret_key = config.secret_key
app.config["UPLOAD_FOLDER"] = "uploads"

# Auto-create uploads folder if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

GENRES = [
    "Pop", "Rock", "Hip-Hop", "R&B", "Jazz", "Classical",
    "Electronic", "Metal", "Country", "Folk", "Reggae",
    "Blues", "Punk", "Indie", "Latin", "Muu"
]

@app.route("/")
def index():
    sql = "SELECT id, title, artist, genre, filename, user FROM songs"
    songs = db.query(sql)
    return render_template("index.html", songs=songs)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/delete_song", methods=["POST"])
def delete_song():
    if "username" not in session:
        return redirect("/login")

    song_id = request.form["song_id"]
    sql = "SELECT filename, user FROM songs WHERE id = ?"
    result = db.query(sql, [song_id])

    if not result:
        flash("Audio not found", "error")
        return redirect("/")

    if result[0][1] != session["username"]:
        flash("Not qualified to delete this", "error")
        return redirect("/")

    filename = result[0][0]
    sql = "DELETE FROM songs WHERE id = ?"
    db.execute(sql, [song_id])

    # Only delete file if no other songs reference the same filename
    sql = "SELECT COUNT(*) FROM songs WHERE filename = ?"
    count = db.query(sql, [filename])[0][0]
    if count == 0:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    flash("Audio deleted", "success")
    return redirect(request.referrer or "/")

@app.route("/new_item")
def new_item():
    if "username" not in session:
        return redirect("/login")
    return render_template("new_item.html", genres=GENRES)

@app.route("/create_item", methods=["POST"])
def create_item():
    if "username" not in session:
        return redirect("/login")

    title = request.form["title"].strip()
    artist = request.form.get("artist", "").strip()
    genre = request.form["genre"].strip()

    if not title:
        flash("Please add title", "error")
        return redirect("/new_item")

    if not genre:
        flash("Please choose genre", "error")
        return redirect("/new_item")

    file = request.files["file"]
    if not file or not file.filename.endswith(".mp3"):
        flash("File must be .mp3", "error")
        return redirect("/new_item")

    # Insert first to get the auto-generated song_id, then use it as filename
    sql = "INSERT INTO songs (title, artist, genre, filename, user) VALUES (?, ?, ?, ?, ?)"
    db.execute(sql, [title, artist, genre, "_tmp", session["username"]])
    song_id = db.last_insert_id()

    filename = f"{song_id}.mp3"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    sql = "UPDATE songs SET filename = ? WHERE id = ?"
    db.execute(sql, [filename, song_id])

    flash("Audio added", "success")
    return redirect("/")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/create", methods=["POST"])
def create():
    username = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    if password1 != password2:
        flash("Passwords dont match", "error")
        return redirect("/register")

    password_hash = generate_password_hash(password1)
    try:
        sql = "INSERT INTO users (username, password_hash) VALUES (?, ?)"
        db.execute(sql, [username, password_hash])
    except sqlite3.IntegrityError:
        flash("Username already in use", "error")
        return redirect("/register")

    session["username"] = username
    flash(f"Welcome, {username}!", "success")
    return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form["username"]
    password = request.form["password"]

    sql = "SELECT password_hash FROM users WHERE username = ?"
    result = db.query(sql, [username])

    if not result or not check_password_hash(result[0][0], password):
        flash("Wrong username or password", "error")
        return redirect("/login")

    session["username"] = username
    flash(f"Welcome back, {username}!", "success")
    return redirect("/")

@app.route("/search")
def search():
    query = request.args.get("query", "")
    sql = "SELECT id, title, artist, genre, filename, user FROM songs WHERE title LIKE ? OR genre LIKE ? OR artist LIKE ? OR user LIKE ?"
    songs = db.query(sql, [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])
    return render_template("index.html", songs=songs, search_query=query)

@app.route("/song/<int:song_id>")
def song_page(song_id):
    sql = "SELECT id, title, artist, genre, filename, user FROM songs WHERE id = ?"
    result = db.query(sql, [song_id])

    if not result:
        abort(404)

    song = result[0]
    sql = """
        SELECT c.id, c.content, c.created, c.user
        FROM comments c
        WHERE c.song_id = ?
        ORDER BY c.created ASC
    """
    comments = db.query(sql, [song_id])
    return render_template("song.html", song=song, comments=comments)

@app.route("/add_comment", methods=["POST"])
def add_comment():
    if "username" not in session:
        return redirect("/login")

    content = request.form["content"].strip()
    song_id = request.form["song_id"]

    if not content:
        flash("Comment cant be empty.", "error")
        return redirect(request.referrer or "/")

    sql = "INSERT INTO comments (content, song_id, user) VALUES (?, ?, ?)"
    db.execute(sql, [content, song_id, session["username"]])
    return redirect(request.referrer or "/")

@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect("/login")
    return redirect(f"/user/{session['username']}")

@app.route("/user/<username>")
def user_profile(username):
    sql = "SELECT id FROM users WHERE username = ?"
    user = db.query(sql, [username])
    if not user:
        abort(404)

    sql = "SELECT id, title, artist, genre, filename, user FROM songs WHERE user = ?"
    songs = db.query(sql, [username])

    sql = """
        SELECT c.id, c.content, c.created, s.title as song_title, c.song_id, c.user
        FROM comments c
        JOIN songs s ON c.song_id = s.id
        WHERE c.user = ?
        ORDER BY c.created DESC
        LIMIT 50
    """
    comments = db.query(sql, [username])
    return render_template("profile.html", songs=songs, comments=comments, profile_user=username)

@app.route("/delete_comment", methods=["POST"])
def delete_comment():
    if "username" not in session:
        return redirect("/login")

    comment_id = request.form["comment_id"]
    sql = "SELECT user FROM comments WHERE id = ?"
    result = db.query(sql, [comment_id])

    if result and result[0][0] == session["username"]:
        sql = "DELETE FROM comments WHERE id = ?"
        db.execute(sql, [comment_id])
        flash("Comment deleted", "success")

    return redirect(request.referrer or "/")

@app.route("/logout")
def logout():
    del session["username"]
    flash("Logged out", "success")
    return redirect("/")

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404