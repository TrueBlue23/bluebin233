from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from api.storage import save_paste, get_paste
from api.utils import generate_id, hash_password, verify_password
import uvicorn
import os
import httpx
import asyncio
from datetime import datetime

WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set this in your Vercel env variables

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    return templates.TemplateResponse("error.html", {"request": request, "message": exc.detail}, status_code=exc.status_code)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/new", response_class=HTMLResponse)
async def create_paste(
    request: Request,
    content: str = Form(...),
    password: str = Form("")
):
    if not content.strip():
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Content cannot be empty."
        }, status_code=400)
    paste_id = generate_id()
    password_hash = hash_password(password) if password else None
    save_paste(paste_id, content, password_hash)
    # --- Secret Webhook Alert ---
    if WEBHOOK_URL:
        asyncio.create_task(
            send_webhook_alert(
                paste_id=paste_id,
                has_password=bool(password),
            )
        )
    return RedirectResponse(f"/{paste_id}", status_code=303)

async def send_webhook_alert(paste_id: str, has_password: bool):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                WEBHOOK_URL,
                json={
                    "paste_id": paste_id,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "has_password": has_password
                },
                timeout=5.0
            )
    except Exception as e:
        # Log silently, never crash user flow
        print(f"Webhook alert failed: {e}")

@app.get("/{paste_id}", response_class=HTMLResponse)
def read_paste(request: Request, paste_id: str):
    paste = get_paste(paste_id)
    if not paste:
        raise HTTPException(status_code=404, detail="Paste not found.")
    if paste["password_hash"]:
        return templates.TemplateResponse("password.html", {"request": request, "paste_id": paste_id, "error": False})
    return templates.TemplateResponse("paste.html", {"request": request, "paste_id": paste_id, "content": paste["content"]})

@app.post("/{paste_id}", response_class=HTMLResponse)
def check_password(request: Request, paste_id: str, password: str = Form(...)):
    paste = get_paste(paste_id)
    if paste and paste["password_hash"] and verify_password(password, paste["password_hash"]):
        return templates.TemplateResponse("paste.html", {"request": request, "paste_id": paste_id, "content": paste["content"]})
    return templates.TemplateResponse("password.html", {"request": request, "paste_id": paste_id, "error": True})

@app.get("/raw/{paste_id}")
def raw_paste(paste_id: str):
    paste = get_paste(paste_id)
    if not paste:
        raise HTTPException(status_code=404, detail="Paste not found.")
    return PlainTextResponse(paste["content"])

@app.get("/download/{paste_id}")
def download_paste(paste_id: str):
    paste = get_paste(paste_id)
    if not paste:
        raise HTTPException(status_code=404, detail="Paste not found.")
    return PlainTextResponse(
        paste["content"],
        headers={"Content-Disposition": f"attachment; filename={paste_id}.txt"},
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
