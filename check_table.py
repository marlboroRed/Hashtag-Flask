import sqlite3

DB_PATH = 'requests.db'

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    print("현재 DB에 존재하는 테이블:")
    for table in tables:
        print("-", table[0])
