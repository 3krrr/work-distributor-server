from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

DB_FILE = "worknet.db"

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# DB 초기화(최초 1회)
def init_db():
    conn = db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            name TEXT,
            phone TEXT,
            role INTEGER DEFAULT 0,
            approved INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT,
            to_user TEXT,
            title TEXT,
            content TEXT,
            status TEXT DEFAULT '받음'
        )
    ''')
    conn.commit()
    conn.close()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

init_db()

@app.post("/signup")
def signup(
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...)
):
    conn = db()
    c = conn.cursor()
    # 이미 존재하는 유저 체크
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
    # 첫 회원가입자는 관리자(1)로 등록
    c.execute("SELECT COUNT(*) FROM users",)
    first = c.fetchone()[0] == 0
    role = 1 if first else 0
    approved = 1 if first else 0
    c.execute("INSERT INTO users (username, password, name, phone, role, approved) VALUES (?, ?, ?, ?, ?, ?)",
              (username, password, name, phone, role, approved))
    conn.commit()
    conn.close()
    return {"result": "ok"}

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT username, name, role, approved FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="아이디/비밀번호 오류")
    if not user["approved"]:
        raise HTTPException(status_code=401, detail="아직 승인되지 않았습니다.")
    return {
        "username": user["username"],
        "name": user["name"],
        "role": user["role"]
    }

@app.get("/members")
def get_members():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT username, name, phone, role FROM users WHERE approved = 1")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"members": rows}

@app.get("/pending_users")
def get_pending_users():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT username, name, phone FROM users WHERE approved = 0")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"users": rows}

@app.post("/approve_user")
def approve_user(username: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE users SET approved = 1 WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/remove_user")
def remove_user(username: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/send_message")
def send_message(
    from_user: str = Form(...), 
    to_user: str = Form(...),
    title: str = Form(...),
    content: str = Form(...)
):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT INTO messages (from_user, to_user, title, content) VALUES (?, ?, ?, ?)",
              (from_user, to_user, title, content))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/sent_messages")
def sent_messages(username: str):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM messages WHERE from_user = ?", (username,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"messages": rows}

@app.get("/received_messages")
def received_messages(username: str):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM messages WHERE to_user = ?", (username,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"messages": rows}
