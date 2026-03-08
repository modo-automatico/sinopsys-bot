import os
import httpx
import json
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
security = HTTPBasic()

# --- Banco de Dados Local (JSON) ---
DB_FILE = os.path.join(BASE_DIR, "database.json")

def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {"atendimento": "sinopsys2026"}, "automations": [], "logs": []}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        # Garantir que campos novos existam
        if "automations" not in data: data["automations"] = []
        for auto in data["automations"]:
            if "count_comments" not in auto: auto["count_comments"] = 0
            if "count_dms" not in auto: auto["count_dms"] = 0
        return data

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- Segurança ---
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    db = load_db()
    correct_password = db["users"].get(credentials.username)
    if not (correct_password and credentials.password == correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorreto usuário ou senha",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- Configurações de API ---
PAGE_ACCESS_TOKEN = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", "")

# --- Lógica de Negócio ---

async def send_dm(recipient_id: str, text: str):
    # Tratar IDs de teste da Meta para não dar erro
    if not recipient_id or recipient_id in ["232323232", "12334"]:
        print(f"DM Simulada para ID {recipient_id}: {text}")
        return {"status": "simulated"}

    url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        return resp.json()

async def reply_to_comment(comment_id: str, text: str):
    # Tratar IDs de teste da Meta
    if not comment_id or "17865" in comment_id:
        print(f"Resposta de Comentário Simulada para ID {comment_id}: {text}")
        return {"status": "simulated"}

    url = f"https://graph.facebook.com/v21.0/{comment_id}/replies?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"message": text}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        return resp.json()

# --- Rotas da Interface ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(get_current_username)):
    db = load_db()
    automations = sorted(db["automations"], key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Formatação de datas para o template
    for auto in automations:
        dt = datetime.fromisoformat(auto['created_at'])
        auto['date_display'] = dt.strftime("%d/%m/%Y %H:%M")
        if auto.get('last_trigger'):
            lt = datetime.fromisoformat(auto['last_trigger'])
            auto['last_display'] = lt.strftime("%d/%m/%Y %H:%M")
        else:
            auto['last_display'] = "Aguardando..."

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "automations": automations,
        "username": username,
        "brand_color": "#f89800"
    })

@app.post("/add-automation")
async def add_automation(
    keyword: str = Form(...),
    comment_reply: str = Form(...),
    dm_text: str = Form(...),
    username: str = Depends(get_current_username)
):
    db = load_db()
    keyword = keyword.strip().lower()
    
    if any(a['keyword'] == keyword for a in db["automations"]):
        return HTMLResponse("<script>alert('Já existe uma automação para esta palavra-chave!'); window.location='/';</script>")

    new_auto = {
        "id": str(uuid.uuid4()),
        "keyword": keyword,
        "comment_reply": comment_reply,
        "dm_text": dm_text,
        "created_at": datetime.now().isoformat(),
        "last_trigger": None,
        "count_comments": 0,
        "count_dms": 0
    }
    db["automations"].append(new_auto)
    save_db(db)
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete/{auto_id}")
async def delete_automation(auto_id: str, username: str = Depends(get_current_username)):
    db = load_db()
    db["automations"] = [a for a in db["automations"] if a["id"] != auto_id]
    save_db(db)
    return RedirectResponse(url="/", status_code=303)

# --- Webhook ---

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == os.getenv("INSTAGRAM_VERIFY_TOKEN"):
        return int(params.get("hub.challenge"))
    return "Token Inválido"

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        body = await request.body()
        data = json.loads(body)
        db = load_db()
        
        print(f"\n[WEBHOOK] Novo evento recebido às {datetime.now().strftime('%H:%M:%S')}")

        if "entry" in data:
            for entry in data["entry"]:
                if "changes" in entry:
                    for change in entry["changes"]:
                        field = change.get("field")
                        value = change.get("value", {})
                        
                        if field in ["comments", "feed"]:
                            if field == "feed" and value.get("item") != "comment":
                                continue
                            
                            comment_id = value.get("id") or value.get("comment_id")
                            user_comment = value.get("text", "").lower().strip() or value.get("message", "").lower().strip()
                            sender_id = value.get("from", {}).get("id") or value.get("sender_id")

                            if not user_comment: continue

                            print(f"💬 Comentário detectado no campo '{field}': '{user_comment}'")
                            
                            for auto in db["automations"]:
                                if auto["keyword"].lower().strip() in user_comment:
                                    print(f"✅ MATCH ENCONTRADO: '{auto['keyword']}'")
                                    await reply_to_comment(comment_id, auto["comment_reply"])
                                    await send_dm(sender_id, auto["dm_text"])
                                    
                                    auto["count_comments"] += 1
                                    auto["count_dms"] += 1
                                    auto["last_trigger"] = datetime.now().isoformat()
                                    save_db(db)
                                    break
    except Exception as e:
        print(f"🚨 Erro no webhook: {e}")

    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
