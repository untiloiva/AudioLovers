import os
import sqlite3
from flask import Flask
from flask import redirect, render_template, request, session
from flask import send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
import config
import db

app = Flask(__name__)
app.secret_key = config.secret_key
app.config["UPLOAD_FOLDER"] = "uploads"

@app.route("/")
def index():
    sql = "SELECT id, name, artist, genre, filename, user FROM songs"
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
    if result and result[0][1] == session["username"]:
        filename = result[0][0]
        sql = "DELETE FROM songs WHERE id = ?"
        db.execute(sql, [song_id])
        os.remove(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    return redirect("/")

@app.route("/new_item")
def new_item():
    if "username" not in session:
        return redirect("/login")
    return render_template("new_item.html")

@app.route("/create_item", methods=["POST"])
def create_item():
    if "username" not in session:
        return redirect("/login")
    title = request.form["title"]
    artist = request.form.get("artist", "")
    genre = request.form["genre"]
    file = request.files["file"]
    if file and file.filename.endswith(".mp3"):
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        sql = "INSERT INTO songs (name, artist, genre, filename, user) VALUES (?, ?, ?, ?, ?)"
        db.execute(sql, [title, artist, genre, file.filename, session["username"]])
        return redirect("/")
    return "VIRHE: tiedosto ei ole mp3"

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/create", methods=["POST"])
def create():
    username = request.form["username"]
    password1 = request.form["password1"]
    password2 = request.form["password2"]
    if password1 != password2:
        return "VIRHE: salasanat eivät ole samat"
    password_hash = generate_password_hash(password1)
    try:
        sql = "INSERT INTO users (username, password_hash) VALUES (?, ?)"
        db.execute(sql, [username, password_hash])
    except sqlite3.IntegrityError:
        return "VIRHE: tunnus on jo varattu"
    session["username"] = username
    return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        sql = "SELECT password_hash FROM users WHERE username = ?"
        result = db.query(sql, [username])
        if not result:
            return "VIRHE: väärä tunnus tai salasana"
        password_hash = result[0][0]
        if check_password_hash(password_hash, password):
            session["username"] = username
            return redirect("/")
        else:
            return "VIRHE: väärä tunnus tai salasana"

@app.route("/search")
def search():
    query = request.args.get("query", "")
    sql = "SELECT id, name, artist, genre, filename, user FROM songs WHERE name LIKE ? OR genre LIKE ? OR artist LIKE ? OR user LIKE ?"
    songs = db.query(sql, [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])
    return render_template("index.html", songs=songs)

@app.route("/song/<int:song_id>")
def song_page(song_id):
    sql = "SELECT id, name, artist, genre, filename, user FROM songs WHERE id = ?"
    song = db.query(sql, [song_id])[0]
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
    content = request.form["content"]
    song_id = request.form["song_id"]
    sql = "INSERT INTO comments (content, song_id, user) VALUES (?, ?, ?)"
    db.execute(sql, [content, song_id, session["username"]])
    return redirect(request.referrer or "/")

@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect("/login")
    sql = "SELECT id, name, artist, genre, filename, user FROM songs WHERE user = ?"
    songs = db.query(sql, [session["username"]])
    sql = """
        SELECT c.id, c.content, c.created, s.name as song_title , c.song_id
        FROM comments c 
        JOIN songs s ON c.song_id = s.id 
        WHERE c.user = ? 
        ORDER BY c.created DESC 
        LIMIT 50
    """
    comments = db.query(sql, [session["username"]])
    return render_template("profile.html", songs=songs, comments=comments)

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
    return redirect(request.referrer or "/")

@app.route("/logout")
def logout():
    del session["username"]
    return redirect("/")
