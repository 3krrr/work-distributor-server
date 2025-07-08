# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
import hashlib

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    name = Column(String)
    phone = Column(String)
    role = Column(Integer, default=2)
    approved = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

active_connections = {}

@app.post("/signup")
def signup(username: str = Form(), password: str = Form(), name: str = Form(), phone: str = Form()):
    db = SessionLocal()
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(status_code=400, detail="아이디 중복")
    hashpw = hashlib.sha256(password.encode()).hexdigest()
    user = User(username=username, password=hashpw, name=name, phone=phone, approved=False, role=2)
    db.add(user)
    db.commit()
    return {"msg": "승인 대기"}

@app.post("/approve_user")
def approve_user(username: str = Form(), approver: str = Form()):
    db = SessionLocal()
    admin = db.query(User).filter_by(username=approver, approved=True, role=1).first()
    if not admin:
        raise HTTPException(status_code=403, detail="권한 없음")
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자 없음")
    user.approved = True
    db.commit()
    return {"msg": "승인완료"}

@app.post("/login")
def login(username: str = Form(), password: str = Form()):
    db = SessionLocal()
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=401, detail="아이디 없음")
    if not user.approved:
        raise HTTPException(status_code=401, detail="미승인")
    hashpw = hashlib.sha256(password.encode()).hexdigest()
    if user.password != hashpw:
        raise HTTPException(status_code=401, detail="비밀번호 불일치")
    return {"msg": "로그인 성공", "username": user.username, "role": user.role, "name": user.name}

@app.websocket("/ws/{username}")
async def websocket_endpoint(websocket: WebSocket, username: str):
    await websocket.accept()
    active_connections[username] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            print(f"[DEBUG] {username}에서 수신: {data}")
            await websocket.send_text(f"서버에서 받은 데이터: {data}")
    except WebSocketDisconnect:
        del active_connections[username]
        print(f"[DEBUG] {username} 연결 종료")

@app.get("/")
def read_root():
    return {"status": "서버 정상 작동 중"}
