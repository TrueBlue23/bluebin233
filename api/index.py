from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import secrets
import string
import os

app = FastAPI()
# Correctly resolve relative paths for Vercel deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)

app.mount("/static", StaticFiles(directory=os.path.join(PARENT_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(PARENT_DIR, "templates"))

# In-memory storage (lost on restart)
PASTES = {}  # id: {content, private, password, created}

def gen_id():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))

def is_valid_pw(pw):
    return pw.isdigit() and len(pw) == 4

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/pastebin", response_class=HTMLResponse)
async def pastebin(request: Request):
    return templates.TemplateResponse("pastebin.html", {"request": request})

@app.get("/pastebin/create", response_class=HTMLResponse)
async def create_paste_page(request: Request):
    return templates.TemplateResponse("create.html", {"request": request, "error": None, "link": None})

@app.post("/pastebin/create", response_class=HTMLResponse)
async def create_paste(request: Request, content: str = Form(...), password: str = Form("")):
    if not content.strip():
        return templates.TemplateResponse("create.html", {"request": request, "error": "Paste cannot be empty!", "link": None})
    if password and not is_valid_pw(password):
        return templates.TemplateResponse("create.html", {"request": request, "error": "Password must be 4 digits.", "link": None})
    paste_id = gen_id()
    PASTES[paste_id] = {
        "content": content,
        "private": bool(password),
        "password": password if password else None,
    }
    link = f"/pastebin/{paste_id}"
    return templates.TemplateResponse("create.html", {"request": request, "error": None, "link": link})

@app.get("/pastebin/view", response_class=HTMLResponse)
async def view_page(request: Request):
    return templates.TemplateResponse("view.html", {"request": request, "error": None, "content": None})

@app.post("/pastebin/view", response_class=HTMLResponse)
async def view_paste(request: Request, link: str = Form(...), password: str = Form("")):
    paste_id = link.strip().split("/")[-1]
    paste = PASTES.get(paste_id)
    if not paste:
        return templates.TemplateResponse("view.html", {"request": request, "error": "Paste not found.", "content": None})
    if paste["private"]:
        if not is_valid_pw(password) or password != paste["password"]:
            return templates.TemplateResponse("password.html", {"request": request, "paste_id": paste_id, "error": "Password required or incorrect!"})
    return templates.TemplateResponse("reveal.html", {"request": request, "content": paste["content"], "paste_id": paste_id, "private": paste["private"]})

@app.get("/pastebin/{paste_id}", response_class=HTMLResponse)
async def reveal(request: Request, paste_id: str):
    paste = PASTES.get(paste_id)
    if not paste:
        return templates.TemplateResponse("error.html", {"request": request, "message": "Paste not found."})
    if paste["private"]:
        return templates.TemplateResponse("password.html", {"request": request, "paste_id": paste_id, "error": None})
    return templates.TemplateResponse("reveal.html", {"request": request, "content": paste["content"], "paste_id": paste_id, "private": False})

@app.post("/pastebin/{paste_id}", response_class=HTMLResponse)
async def reveal_pw(request: Request, paste_id: str, password: str = Form(...)):
    paste = PASTES.get(paste_id)
    if not paste:
        return templates.TemplateResponse("error.html", {"request": request, "message": "Paste not found."})
    if not is_valid_pw(password) or password != paste["password"]:
        return templates.TemplateResponse("password.html", {"request": request, "paste_id": paste_id, "error": "Incorrect password."})
    return templates.TemplateResponse("reveal.html", {"request": request, "content": paste["content"], "paste_id": paste_id, "private": True})

@app.get("/raw/{paste_id}")
async def raw_view(paste_id: str):
    paste = PASTES.get(paste_id)
    if not paste:
        raise HTTPException(status_code=404, detail="Paste not found.")
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Access-Control-Allow-Origin": "*"
    }
    return Response(paste["content"], headers=headers)
