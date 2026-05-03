import os
import sqlite3
from flask import Flask
from flask import redirect, render_template, request, session, flash, abort
from flask import send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import config
import db

app = Flask(__name__)
app.secret_key = config.secret_key
app.config["UPLOAD_FOLDER"] = "uploads"

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

# Auto-create upload folders
os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "avatars"), exist_ok=True)
os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "covers"), exist_ok=True)

GENRES = [
    "Pop", "Rock", "Hip-Hop", "R&B", "Jazz", "Classical",
    "Electronic", "Metal", "Country", "Folk", "Reggae",
    "Blues", "Punk", "Indie", "Latin", "Other"
]

def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

@app.route("/")
def index():
    sql = "SELECT id, title, artist, genre, filename, user, cover_image FROM songs"
    songs = db.query(sql)
    return render_template("index.html", songs=songs)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/delete_song", methods=["POST"])
def delete_song():
    if "username" not in session:
        return redirect("/login")

    song_id = request.form["song_id"]
    sql = "SELECT filename, cover_image, user FROM songs WHERE id = ?"
    result = db.query(sql, [song_id])

    if not result:
        flash("Audio not found.", "error")
        return redirect("/")

    if result[0]["user"] != session["username"]:
        flash("Not authorized to delete this.", "error")
        return redirect("/")

    filename = result[0]["filename"]
    cover_image = result[0]["cover_image"]

    sql = "DELETE FROM songs WHERE id = ?"
    db.execute(sql, [song_id])

    # Only delete audio file if no other songs reference it
    sql = "SELECT COUNT(*) FROM songs WHERE filename = ?"
    count = db.query(sql, [filename])[0][0]
    if count == 0:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    # Delete cover image
    if cover_image:
        cover_path = os.path.join(app.config["UPLOAD_FOLDER"], "covers", cover_image)
        if os.path.exists(cover_path):
            os.remove(cover_path)

    flash("Audio deleted.", "success")
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
        flash("Title cannot be empty.", "error")
        return redirect("/new_item")
    if not genre:
        flash("Genre cannot be empty.", "error")
        return redirect("/new_item")

    file = request.files["file"]
    if not file or not file.filename.endswith(".mp3"):
        flash("File must be in MP3 format.", "error")
        return redirect("/new_item")

    # Insert first to get song_id, use it as filename
    sql = "INSERT INTO songs (title, artist, genre, filename, cover_image, user) VALUES (?, ?, ?, ?, ?, ?)"
    db.execute(sql, [title, artist, genre, "_tmp", None, session["username"]])
    song_id = db.last_insert_id()

    filename = f"{song_id}.mp3"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    # Handle optional cover image
    cover_filename = None
    cover_file = request.files.get("cover_image")
    if cover_file and cover_file.filename and allowed_image(cover_file.filename):
        ext = cover_file.filename.rsplit(".", 1)[1].lower()
        cover_filename = f"{song_id}.{ext}"
        cover_file.save(os.path.join(app.config["UPLOAD_FOLDER"], "covers", cover_filename))

    sql = "UPDATE songs SET filename = ?, cover_image = ? WHERE id = ?"
    db.execute(sql, [filename, cover_filename, song_id])

    flash("Audio added successfully!", "success")
    return redirect("/")

@app.route("/upload_avatar", methods=["POST"])
def upload_avatar():
    if "username" not in session:
        return redirect("/login")

    file = request.files.get("avatar")
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(f"/user/{session['username']}")

    if not allowed_image(file.filename):
        flash("File must be an image (jpg, png, webp, gif).", "error")
        return redirect(f"/user/{session['username']}")

    # Delete old avatar
    sql = "SELECT avatar FROM users WHERE username = ?"
    result = db.query(sql, [session["username"]])
    if result and result[0]["avatar"]:
        old_path = os.path.join(app.config["UPLOAD_FOLDER"], "avatars", result[0]["avatar"])
        if os.path.exists(old_path):
            os.remove(old_path)

    ext = file.filename.rsplit(".", 1)[1].lower()
    avatar_filename = f"{session['username']}.{ext}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], "avatars", avatar_filename))

    sql = "UPDATE users SET avatar = ? WHERE username = ?"
    db.execute(sql, [avatar_filename, session["username"]])

    flash("Profile picture updated!", "success")
    return redirect(f"/user/{session['username']}")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/create", methods=["POST"])
def create():
    username = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]

    if password1 != password2:
        flash("Passwords do not match.", "error")
        return redirect("/register")

    password_hash = generate_password_hash(password1)
    try:
        sql = "INSERT INTO users (username, password_hash) VALUES (?, ?)"
        db.execute(sql, [username, password_hash])
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

    username = request.form["username"]
    password = request.form["password"]

    sql = "SELECT password_hash FROM users WHERE username = ?"
    result = db.query(sql, [username])

    if not result or not check_password_hash(result[0][0], password):
        flash("Wrong username or password.", "error")
        return redirect("/login")

    session["username"] = username
    flash(f"Welcome back, {username}!", "success")
    return redirect("/")

@app.route("/search")
def search():
    query = request.args.get("query", "")
    sql = "SELECT id, title, artist, genre, filename, user, cover_image FROM songs WHERE title LIKE ? OR genre LIKE ? OR artist LIKE ? OR user LIKE ?"
    songs = db.query(sql, [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])
    return render_template("index.html", songs=songs, search_query=query)

@app.route("/song/<int:song_id>")
def song_page(song_id):
    sql = "SELECT id, title, artist, genre, filename, user, cover_image FROM songs WHERE id = ?"
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
        flash("Comment cannot be empty.", "error")
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
    sql = "SELECT id, avatar FROM users WHERE username = ?"
    user = db.query(sql, [username])
    if not user:
        abort(404)

    avatar = user[0]["avatar"]

    sql = "SELECT id, title, artist, genre, filename, user, cover_image FROM songs WHERE user = ?"
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
    return render_template("profile.html", songs=songs, comments=comments, profile_user=username, avatar=avatar)

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
        flash("Comment deleted.", "success")

    return redirect(request.referrer or "/")

@app.route("/logout")
def logout():
    del session["username"]
    flash("You have been logged out.", "success")
    return redirect("/")

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404