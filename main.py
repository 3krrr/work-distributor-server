from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

DB_FILE = "worknet.db"

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    c = conn.cursor()
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            name TEXT,
            phone TEXT,
            role_id INTEGER,
            approved INTEGER DEFAULT 0,
            FOREIGN KEY(role_id) REFERENCES roles(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT,
            to_users TEXT, -- 콤마로 구분된 유저명
            title TEXT,
            content TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            username TEXT,
            comment TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 최초 관리자/직책 자동생성
    c.execute("SELECT COUNT(*) FROM roles")
    if c.fetchone()[0] == 0:
        c.execute('''INSERT INTO roles (name, can_approve, can_edit_role_name, can_edit_user_role, can_edit_role_permissions, can_send_message)
                  VALUES ('관리자', 1, 1, 1, 1, 1)''')
        c.execute('''INSERT INTO roles (name, can_approve, can_edit_user_role, can_send_message)
                  VALUES ('일반', 0, 0, 1)''')
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
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
    # 첫 유저는 무조건 관리자, 아니면 일반
    c.execute("SELECT COUNT(*) FROM users")
    first = c.fetchone()[0] == 0
    if first:
        c.execute("SELECT id FROM roles WHERE name='관리자'")
        role_id = c.fetchone()[0]
        approved = 1
    else:
        c.execute("SELECT id FROM roles WHERE name='일반'")
        role_id = c.fetchone()[0]
        approved = 0
    c.execute("INSERT INTO users (username, password, name, phone, role_id, approved) VALUES (?, ?, ?, ?, ?, ?)",
              (username, password, name, phone, role_id, approved))
    conn.commit()
    conn.close()
    return {"result": "ok"}

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("""SELECT u.username, u.name, u.phone, u.approved, r.id as role_id, r.name as role_name,
        r.can_approve, r.can_edit_role_name, r.can_edit_user_role, r.can_edit_role_permissions, r.can_send_message
        FROM users u JOIN roles r ON u.role_id = r.id
        WHERE u.username = ? AND u.password = ?""", (username, password))
    user = c.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="아이디/비밀번호 오류")
    if not user["approved"]:
        raise HTTPException(status_code=401, detail="아직 승인되지 않았습니다.")
    return dict(user)

@app.get("/roles")
def get_roles():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM roles")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"roles": rows}

@app.post("/edit_role_name")
def edit_role_name(role_id: int = Form(...), new_name: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE roles SET name = ? WHERE id = ?", (new_name, role_id))
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
    c.execute("""UPDATE roles SET can_approve=?, can_edit_role_name=?, can_edit_user_role=?, can_edit_role_permissions=?, can_send_message=?
                 WHERE id=?""", (can_approve, can_edit_role_name, can_edit_user_role, can_edit_role_permissions, can_send_message, role_id))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/members")
def get_members():
    conn = db()
    c = conn.cursor()
    c.execute("""SELECT u.username, u.name, u.phone, r.name as role_name, r.id as role_id
        FROM users u JOIN roles r ON u.role_id = r.id WHERE u.approved = 1""")
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

@app.post("/edit_user_role")
def edit_user_role(username: str = Form(...), new_role_id: int = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("UPDATE users SET role_id = ? WHERE username = ?", (new_role_id, username))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.post("/send_message")
def send_message(
    from_user: str = Form(...), 
    to_users: str = Form(...),
    title: str = Form(...),
    content: str = Form(...)
):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT INTO messages (from_user, to_users, title, content) VALUES (?, ?, ?, ?)",
              (from_user, to_users, title, content))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/received_messages")
def received_messages(username: str):
    conn = db()
    c = conn.cursor()
    c.execute("""SELECT * FROM messages WHERE ','||to_users||',' LIKE ?""", (f'%,{username},%',))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"messages": rows}

@app.get("/sent_messages")
def sent_messages(username: str):
    conn = db()
    c = conn.cursor()
    c.execute("""SELECT * FROM messages WHERE from_user=?""", (username,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"messages": rows}

@app.get("/comments")
def get_comments(message_id: int):
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM comments WHERE message_id = ? ORDER BY created", (message_id,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"comments": rows}

@app.post("/add_comment")
def add_comment(message_id: int = Form(...), username: str = Form(...), comment: str = Form(...)):
    conn = db()
    c = conn.cursor()
    c.execute("INSERT INTO comments (message_id, username, comment) VALUES (?, ?, ?)", (message_id, username, comment))
    conn.commit()
    conn.close()
    return {"status": "ok"}
