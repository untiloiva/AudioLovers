import os
import sqlite3
from flask import Flask
from flask import redirect, render_template, request, session
from werkzeug.security import generate_password_hash, check_password_hash
import config
import db
from flask import send_from_directory

app = Flask(__name__)
app.secret_key = config.secret_key
app.config["UPLOAD_FOLDER"] = "uploads"

@app.route("/")
def index():
    sql = "SELECT name, genre, filename, user FROM songs"
    songs = db.query(sql)
    return render_template("index.html", songs=songs)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/delete_song", methods=["POST"])
def delete_song():
    if "username" not in session:
        return redirect("/login")
    filename = request.form["filename"]
    sql = "SELECT user FROM songs WHERE filename = ?"
    result = db.query(sql, [filename])
    if result and result[0][0] == session["username"]:
        sql = "DELETE FROM songs WHERE filename = ?"
        db.execute(sql, [filename])
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
    name = request.form["name"]
    genre = request.form["genre"]
    file = request.files["file"]
    if file and file.filename.endswith(".mp3"):
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        sql = "INSERT INTO songs (name, genre, filename, user) VALUES (?, ?, ?, ?)"
        db.execute(sql, [name, genre, file.filename, session["username"]])
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
    return "Tunnus luotu"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        sql = "SELECT password_hash FROM users WHERE username = ?"
        password_hash = db.query(sql, [username])[0][0]
        if check_password_hash(password_hash, password):
            session["username"] = username
            return redirect("/")
        else:
            return "VIRHE: väärä tunnus tai salasana"

@app.route("/logout")
def logout():
    del session["username"]
    return redirect("/")