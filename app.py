from flask import Flask, request, render_template, g, abort
import openai
import sqlite3
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path="C:/Users/user/Desktop/hashtag-app/.env")

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DB_PATH = 'requests.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

with sqlite3.connect(DB_PATH) as conn:
    conn.execute('''
        CREATE TABLE IF NOT EXISTS request_logs (
            ip TEXT,
            menu TEXT,
            date TEXT,
            count INTEGER,
            PRIMARY KEY (ip, menu, date)
        )
    ''')

def cleanup_old_logs(days=30):
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    db.execute("DELETE FROM request_logs WHERE date < ?", (cutoff,))
    db.commit()

def check_limit(ip, menu):
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    cleanup_old_logs()
    db = get_db()

    row = db.execute(
        "SELECT count FROM request_logs WHERE ip=? AND menu=? AND substr(date, 1, 10)=?",
        (ip, menu, today_str)
    ).fetchone()

    if row:
        count = row['count']
        if count >= 3:
            return False
        else:
            db.execute(
                "UPDATE request_logs SET count=? WHERE ip=? AND menu=? AND substr(date, 1, 10)=?",
                (count + 1, ip, menu, today_str)
            )
    else:
        db.execute(
            "INSERT INTO request_logs (ip, menu, date, count) VALUES (?, ?, ?, 1)",
            (ip, menu, now.strftime('%Y-%m-%d %H:%M:%S'))
        )
    db.commit()
    return True

@app.route("/")
def main():
    return render_template("main.html")

@app.route("/title", methods=["GET", "POST"])
def title():
    hashtags = ""
    message = ""
    content = ""

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if not content:
            message = "내용을 입력해주세요."
            return render_template("title.html", hashtags=hashtags, message=message, content="")
        if len(content) > 30:
            message = "제목은 30자 이내로 입력해주세요."
            return render_template("title.html", hashtags=hashtags, message=message, content=content)

        ip = request.remote_addr
        if not check_limit(ip, "title"):
            message = "오늘 무료 제공 횟수를 모두 사용하였습니다. 내일 다시 시도해주세요."
            return render_template("title.html", hashtags=hashtags, message=message, content="")

        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "SNS 글 제목을 기반으로 해시태그 10개만 추천해줘. '#' 붙여서 줄바꿈 없이."},
                    {"role": "user", "content": content}
                ]
            )
            hashtags = response.choices[0].message["content"]
        except Exception:
            message = "해시태그 생성 중 오류가 발생했습니다."

        return render_template("title.html", hashtags=hashtags, message=message, content="")

    return render_template("title.html", hashtags=hashtags, message=message, content="")

@app.route("/theme", methods=["GET", "POST"])
def theme():
    hashtags = ""
    message = ""
    themes = [
        "여행", "일상", "취미", "음식", "운동", "자기계발", "쇼핑", "감성", "디자인", "연애",
        "사진", "카페", "패션", "캠핑", "뷰티", "건강", "인테리어", "게임", "영화", "자연",
        "독서", "공부", "힐링", "노래", "운세", "동물", "아이디어", "스타일", "자전거", "전시"
    ]
    selected_themes = []

    if request.method == "POST":
        selected_themes = request.form.getlist("themes")
        if not selected_themes:
            message = "최소 1개 이상의 테마를 선택해주세요."
            return render_template("theme.html", hashtags=hashtags, themes=themes, selected_themes=[], message=message)

        ip = request.remote_addr
        if not check_limit(ip, "theme"):
            message = "오늘 무료 제공 횟수를 모두 사용하였습니다. 내일 다시 시도해주세요."
            return render_template("theme.html", hashtags=hashtags, themes=themes, selected_themes=[], message=message)

        prompt = f"{', '.join(selected_themes)} 관련 SNS 글에 어울리는 해시태그를 10개 추천해줘. '#' 붙이고 줄바꿈 없이."
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": ', '.join(selected_themes)}
                ]
            )
            hashtags = response.choices[0].message["content"]
        except Exception:
            message = "해시태그 생성 중 오류가 발생했습니다."

        return render_template("theme.html", hashtags=hashtags, themes=themes, selected_themes=[], message=message)

    return render_template("theme.html", hashtags=hashtags, themes=themes, selected_themes=selected_themes, message=message)

@app.route("/admin/stats", methods=["GET", "POST"])
def admin_stats():
    password = request.args.get("pw")
    if password != ADMIN_PASSWORD:
        return abort(403)

    db = get_db()
    if request.method == "POST" and request.form.get("reset") == "1":
        db.execute("UPDATE request_logs SET count = 0")
        db.commit()

    generate_traffic_chart()
    return render_template("admin_stats.html", now=datetime.now)

@app.route("/reward", methods=["POST"])
def reward():
    ip = request.remote_addr
    today = datetime.now().strftime('%Y-%m-%d')
    db = get_db()
    for menu in ["title", "theme"]:
        db.execute("""
            INSERT INTO request_logs (ip, menu, date, count)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(ip, menu, date) DO UPDATE SET count = MAX(count - 1, 0)
        """, (ip, menu, today))
    db.commit()
    return {"message": "1회 추가 기회가 제공되었습니다!"}



import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def generate_traffic_chart():
    db = get_db()
    rows = db.execute("""
        SELECT 
            strftime('%Y-%m-%d %H:%M', datetime(date, '-' || (strftime('%M', date) % 30) || ' minutes')) AS time_block,
            COUNT(*) as count
        FROM request_logs
        WHERE datetime(date) >= datetime('now', '-24 hours')
        GROUP BY time_block
        ORDER BY time_block
    """).fetchall()

    labels = [row["time_block"][-5:] for row in rows if row["time_block"]]
    counts = [row["count"] for row in rows if row["time_block"]]

    plt.figure(figsize=(10, 3))
    plt.plot(labels, counts, marker='o', color='teal')
    plt.title("API Usage (Last 24h, 30min)", fontsize=14)
    plt.xlabel("Time", fontsize=12)
    plt.ylabel("Count", fontsize=12)
    plt.xticks(rotation=45, fontsize=8)
    plt.tight_layout()
    plt.grid(True)
    plt.savefig("static/traffic_chart.png")
    plt.close()

if __name__ == "__main__":
    app.run(debug=True, port=5500)
