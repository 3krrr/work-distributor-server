import os
import uuid
import sqlite3
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

DB_FILE = "worknet.db"
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
    # 사용자 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            name TEXT,
            phone TEXT,
            role_id INTEGER DEFAULT 1,
            approved INTEGER DEFAULT 1
        )
    ''')
    # 직책 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            can_approve INTEGER DEFAULT 0,
            can_edit_role_name INTEGER DEFAULT 0,
            can_edit_user_role INTEGER DEFAULT 0,
            can_edit_role_permissions INTEGER DEFAULT 0,
            can_send_message INTEGER DEFAULT 1
        )
    ''')
    # 메시지 테이블
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT,
            to_users TEXT,
            title TEXT,
            content TEXT,
            attachment TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 메시지 상태 (수신자별)
    c.execute('''
        CREATE TABLE IF NOT EXISTS msg_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            username TEXT,
            status TEXT DEFAULT '확인대기'
        )
    ''')
    # 댓글
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            username TEXT,
            comment TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    # 기본 직책 삽입(없으면)
    c.execute("SELECT COUNT(*) FROM roles")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO roles (name, can_approve, can_send_message) VALUES ('관리자',1,1)")
        c.execute("INSERT INTO roles (name, can_send_message) VALUES ('일반',1)")
        conn.commit()
    conn.close()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
init_db()

### 1. 회원가입/로그인/멤버/직책

@app.post("/signup")
def signup(
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...)
):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    if c.fetchone():
        conn.close()
        raise HTTPException(409, "이미 가입된 아이디입니다.")
    c.execute("INSERT INTO users (username, password, name, phone, role_id, approved) VALUES (?, ?, ?, ?, ?, 0)",
              (username, password, name, phone, 2))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(401, "아이디/비밀번호 불일치")
    if row["approved"] == 0:
        conn.close()
        raise HTTPException(403, "승인 대기중입니다.")
    return dict(row)

@app.get("/members")
def members():
    conn = db()
    c = conn.cursor()
    c.execute('SELECT u.*, r.name as role_name FROM users u LEFT JOIN roles r ON u.role_id=r.id WHERE u.approved=1')
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"members": users}

@app.get("/roles")
def roles():
    conn = db()
    c = conn.cursor()
    c.execute('SELECT * FROM roles')
    roles = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"roles": roles}

@app.post("/edit_user_role")
def edit_user_role(username: str = Form(...), new_role_id: int = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE users SET role_id=? WHERE username=?", (new_role_id, username))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/edit_role_name")
def edit_role_name(role_id: int = Form(...), new_name: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE roles SET name=? WHERE id=?", (new_name, role_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/edit_role_permissions")
def edit_role_permissions(
    role_id: int = Form(...),
    can_approve: int = Form(...),
    can_edit_role_name: int = Form(...),
    can_edit_user_role: int = Form(...),
    can_edit_role_permissions: int = Form(...),
    can_send_message: int = Form(...)
):
    conn = db()
    c = conn.cursor()
    c.execute("""
        UPDATE roles SET can_approve=?, can_edit_role_name=?, can_edit_user_role=?, can_edit_role_permissions=?, can_send_message=?
        WHERE id=?
    """, (can_approve, can_edit_role_name, can_edit_user_role, can_edit_role_permissions, can_send_message, role_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

### 2. 승인/차단/삭제

@app.get("/pending_users")
def pending_users():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE approved=0")
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"users": users}

@app.post("/approve_user")
def approve_user(username: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE users SET approved=1 WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/remove_user")
def remove_user(username: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return {"status": "ok"}

### 3. 메시지

@app.post("/send_message")
async def send_message(
    from_user: str = Form(...),
    to_users: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    file: UploadFile = File(None)
):
    attachment = ""
    if file:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        with open(filepath, "wb") as f:
            f.write(await file.read())
        attachment = filename

    conn = db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (from_user, to_users, title, content, attachment) VALUES (?, ?, ?, ?, ?)",
        (from_user, to_users, title, content, attachment)
    )
    msg_id = c.lastrowid
    for user in to_users.split(","):
        c.execute("INSERT INTO msg_status (message_id, username, status) VALUES (?, ?, ?)", (msg_id, user, '확인대기'))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/received_messages")
def received_messages(username: str):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM messages WHERE ','||to_users||',' LIKE ?", (f'%,{username},%',))
    rows = [dict(row) for row in c.fetchall()]
    for row in rows:
        c.execute("SELECT status FROM msg_status WHERE message_id=? AND username=?", (row["id"], username))
        s = c.fetchone()
        row["my_status"] = s["status"] if s else "확인대기"
        if "created" not in row or not row["created"]:
            row["created"] = ""
    conn.close()
    return {"messages": rows}

@app.get("/sent_messages")
def sent_messages(username: str):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM messages WHERE from_user=? ORDER BY created DESC", (username,))
    msgs = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"messages": msgs}

@app.get("/msg_responses")
def msg_responses(message_id: int):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT username, status FROM msg_status WHERE message_id=?", (message_id,))
    resp = [dict(row) for row in c.fetchall()]
    # 사용자 이름/직책 정보 추가
    c2 = conn.cursor()
    for r in resp:
        c2.execute("SELECT name, role_id FROM users WHERE username=?", (r["username"],))
        u = c2.fetchone()
        if u:
            r["name"] = u["name"]
            r["role_id"] = u["role_id"]
            c2.execute("SELECT name FROM roles WHERE id=?", (u["role_id"],))
            rn = c2.fetchone()
            r["role_name"] = rn["name"] if rn else ""
    conn.close()
    return {"responses": resp}

@app.post("/update_msg_status")
def update_msg_status(message_id: int = Form(...), username: str = Form(...), status: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE msg_status SET status=? WHERE message_id=? AND username=?", (status, message_id, username))
    conn.commit()
    conn.close()
    return {"status": "ok"}

### 4. 댓글/첨부

@app.get("/comments")
def get_comments(message_id: int):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM comments WHERE message_id=? ORDER BY created ASC", (message_id,))
    res = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"comments": res}

@app.post("/add_comment")
def add_comment(message_id: int = Form(...), username: str = Form(...), comment: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT INTO comments (message_id, username, comment) VALUES (?, ?, ?)", (message_id, username, comment))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/download_file/{filename}")
def download_file(filename: str):
    path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=filename)

### 5. 비밀번호 변경

@app.post("/change_password")
def change_password(username: str = Form(...), old_password: str = Form(...), new_password: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, old_password))
    if not c.fetchone():
        conn.close()
        raise HTTPException(400, "기존 비밀번호 불일치")
    c.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
    conn.commit()
    conn.close()
    return {"status": "ok"}
