from flask import Flask
import sqlite3

app = Flask(__name__)

conn = sqlite3.connect("db.sqlite", check_same_thread=False)
cur = conn.cursor()

@app.route("/")
def home():
    try:
        users = cur.execute("SELECT * FROM users").fetchall()
    except:
        users = []

    html = "<h1>🇺🇦 SWGOH ГІЛЬДІЯ DASHBOARD</h1>"
    html += f"<p>Гравців: {len(users)}</p>"
    html += "<h3>Список гравців</h3><ul>"
    for u in users:
        html += f"<li>ID: {u[0]} | роль: {u[1]} | last: {u[2]}</li>"
    html += "</ul>"
    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
