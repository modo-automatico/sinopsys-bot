import os
import httpx
import json
import uuid
import hmac
import hashlib
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, HTTPException, Form, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
security = HTTPBasic()

# --- Banco de Dados Local (JSON) ---
DB_FILE = os.path.join(BASE_DIR, "database.json")

def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "users": {"atendimento": "sinopsys2026"}, 
            "automations": [],
            "logs": [],
            "welcome_config": {"active": False, "text": "Olá {nome}, obrigado por nos seguir! Em que posso ajudar?"}
        }
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "welcome_config" not in data:
                data["welcome_config"] = {"active": False, "text": "Olá {nome}, obrigado por nos seguir!"}
            if "logs" not in data:
                data["logs"] = []
            return data
    except:
        return {"users": {"atendimento": "sinopsys2026"}, "automations": [], "logs": [], "welcome_config": {"active": False}}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def add_log(event_type: str, message: str, metadata: dict = None):
    db = load_db()
    new_log = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "type": event_type, # 'comment', 'dm', 'system', 'error'
        "message": message,
        "metadata": metadata or {}
    }
    db["logs"].insert(0, new_log)
    db["logs"] = db["logs"][:100] # Mantém apenas os últimos 100 logs
    save_db(db)

# --- Segurança ---
META_APP_SECRET = os.getenv("META_APP_SECRET", "")

def verify_signature(body: bytes, signature: str):
    if not META_APP_SECRET: 
        return True # Se não configurado, ignora (para facilitar dev inicial)
    if not signature: 
        return False
    
    try:
        sha_name, signature_hash = signature.split('=')
        if sha_name != 'sha256': 
            return False
        expected_hash = hmac.new(META_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_hash, signature_hash)
    except:
        return False

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    db = load_db()
    correct_password = db["users"].get(credentials.username)
    if not (correct_password and credentials.password == correct_password):
        raise HTTPException(status_code=401, detail="Não autorizado")
    return credentials.username

# --- Funções de API Meta ---
PAGE_ACCESS_TOKEN = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", "")

async def get_user_info(user_id: str):
    if not user_id or len(user_id) < 5 or user_id in ["232323232", "12334"]: return "Cliente"
    url = f"https://graph.facebook.com/v21.0/{user_id}?fields=first_name&access_token={PAGE_ACCESS_TOKEN}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            return resp.json().get("first_name", "Cliente")
    except:
        return "Cliente"

async def like_comment(comment_id: str):
    # Dá um "coração" no comentário
    if not comment_id or "17865" in comment_id: return
    url = f"https://graph.facebook.com/v21.0/{comment_id}?user_likes=true&access_token={PAGE_ACCESS_TOKEN}"
    async with httpx.AsyncClient() as client:
        await client.post(url)

async def send_dm_with_button(recipient_id: str, message_text: str, button_title: str, url: str):
    # Envia uma mensagem com botão de link profissional
    if not recipient_id or recipient_id in ["232323232", "12334"]: return
    
    # Se não houver link, envia texto puro
    if not url:
        payload = {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    else:
        # Template de botão da Meta
        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": message_text,
                        "buttons": [
                            {
                                "type": "web_url",
                                "url": url,
                                "title": button_title or "Acessar Agora"
                            }
                        ]
                    }
                }
            }
        }
    
    graph_url = f"https://graph.facebook.com/v21.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    async with httpx.AsyncClient() as client:
        await client.post(graph_url, json=payload)

async def reply_to_comment(comment_id: str, text: str):
    if not comment_id or "17865" in comment_id: return
    url = f"https://graph.facebook.com/v21.0/{comment_id}/replies?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"message": text}
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def check_token_status():
    if not PAGE_ACCESS_TOKEN:
        return {"status": "error", "message": "Token não configurado no .env"}
    url = f"https://graph.facebook.com/debug_token?input_token={PAGE_ACCESS_TOKEN}&access_token={PAGE_ACCESS_TOKEN}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            data = resp.json().get("data", {})
            if "error" in resp.json():
                error_msg = resp.json()["error"].get("message", "Token Inválido")
                return {"status": "error", "message": f"Erro Meta: {error_msg}"}
            if not data.get("is_valid"):
                return {"status": "error", "message": "Token Expirado ou Inválido"}
            return {"status": "ok", "message": "Conectado à Meta"}
    except:
        return {"status": "warning", "message": "Não foi possível verificar o status"}

# --- Rotas da Interface ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(get_current_username)):
    db = load_db()
    token_info = await check_token_status()
    automations = sorted(db["automations"], key=lambda x: x.get('created_at', ''), reverse=True)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "automations": automations,
        "welcome": db["welcome_config"],
        "username": username,
        "brand_color": "#f89800",
        "token_status": token_info,
        "logs": db.get("logs", [])[:20]
    })

@app.post("/add-automation")
async def add_automation(
    keyword: str = Form(...),
    comment_reply: str = Form(""),
    dm_text: str = Form(""),
    link_url: str = Form(""),
    button_title: str = Form(""),
    active_comment: bool = Form(False),
    active_dm: bool = Form(False),
    auto_like: bool = Form(False),
    auto_id: Optional[str] = Form(None)
):
    db = load_db()
    data = {
        "keyword": keyword.strip().lower(),
        "comment_reply": comment_reply,
        "dm_text": dm_text,
        "link_url": link_url,
        "button_title": button_title or "Ver Mais",
        "active_comment": active_comment,
        "active_dm": active_dm,
        "auto_like": auto_like,
        "created_at": datetime.now().isoformat()
    }

    if auto_id:
        for a in db["automations"]:
            if a["id"] == auto_id:
                a.update(data)
                break
    else:
        data["id"] = str(uuid.uuid4())
        data["count_comments"] = 0
        data["count_dms"] = 0
        db["automations"].append(data)
    
    save_db(db)
    return RedirectResponse(url="/", status_code=303)

@app.post("/save-welcome")
async def save_welcome(
    welcome_text: str = Form(...),
    welcome_active: bool = Form(False)
):
    db = load_db()
    db["welcome_config"] = {"active": welcome_active, "text": welcome_text}
    save_db(db)
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete/{auto_id}")
async def delete_automation(auto_id: str):
    db = load_db()
    db["automations"] = [a for a in db["automations"] if a["id"] != auto_id]
    save_db(db)
    return RedirectResponse(url="/", status_code=303)

# --- Integração Gemini ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
genai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

async def get_gemini_response(user_text: str, user_name: str):
    if not genai_client:
        return f"Olá {user_name}, como posso te ajudar hoje?"
    
    prompt = f"""
    Você é um assistente virtual da Sinopsys Editora no Instagram.
    O cliente se chama {user_name}.
    O cliente disse: "{user_text}"
    
    Responda de forma gentil, profissional e concisa (máximo 2 parágrafos).
    Foque em ser prestativo. Se não souber algo, peça para aguardar um atendente humano.
    """
    
    try:
        response = genai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"Erro Gemini: {e}")
        return f"Olá {user_name}, recebemos sua mensagem e logo um atendente falará com você!"

# --- Webhook ---

@app.post("/webhook")
async def handle_webhook(request: Request):
    # 1. Obter body bruto e assinatura para validação
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    if not verify_signature(body, signature):
        print("❌ Assinatura Inválida!")
        add_log("error", "Tentativa de acesso com assinatura inválida", {"signature": signature})
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    try:
        data = json.loads(body)
        db = load_db()
        
        # Log para depuração em tempo real
        print(f"[{datetime.now().isoformat()}] Webhook recebido: {json.dumps(data)}")

        if "entry" in data:
            for entry in data["entry"]:
                # --- NOVO SEGUIDOR ---
                if "changes" in entry:
                    for change in entry["changes"]:
                        if change.get("field") == "follows":
                            value = change.get("value", {})
                            user_id = value.get("user_id")
                            add_log("system", f"Novo seguidor detectado (ID: {user_id})")
                            if db["welcome_config"]["active"]:
                                nome = await get_user_info(user_id)
                                welcome_msg = db["welcome_config"]["text"].replace("{nome}", nome)
                                await send_dm_with_button(user_id, welcome_msg, "", "")
                                add_log("dm", f"Boas-vindas enviada para {nome}", {"user_id": user_id})

                # --- DMs ---
                if "messaging" in entry:
                    for msg in entry["messaging"]:
                        sender_id = msg.get("sender", {}).get("id")
                        user_text = msg.get("message", {}).get("text", "").lower().strip()
                        if not user_text: continue
                        
                        add_log("dm", f"DM recebida: '{user_text}'", {"sender_id": sender_id})
                        
                        matched = False
                        for auto in db["automations"]:
                            if auto.get("active_dm") and auto["keyword"] in user_text:
                                nome = await get_user_info(sender_id)
                                final_msg = auto['dm_text'].replace("{nome}", nome)
                                await send_dm_with_button(sender_id, final_msg, auto.get("button_title"), auto.get("link_url"))
                                auto["count_dms"] += 1
                                save_db(db)
                                add_log("system", f"Automação disparada (DM): {auto['keyword']}", {"keyword": auto['keyword'], "user": nome})
                                matched = True
                                break
                        
                        if not matched:
                            nome = await get_user_info(sender_id)
                            res_text = await get_gemini_response(user_text, nome)
                            await send_dm_with_button(sender_id, res_text, "", "")
                            add_log("system", f"Resposta Gemini enviada para {nome}", {"input": user_text, "output": res_text})

                # --- COMENTÁRIOS ---
                if "changes" in entry:
                    for change in entry["changes"]:
                        field = change.get("field")
                        value = change.get("value", {})
                        if field in ["comments", "feed"]:
                            comment_id = value.get("id")
                            user_text = value.get("text", "").lower().strip()
                            sender_id = value.get("from", {}).get("id")
                            if not user_text: continue

                            add_log("comment", f"Comentário recebido: '{user_text}'", {"comment_id": comment_id, "sender_id": sender_id})
                            
                            for auto in db["automations"]:
                                if auto.get("active_comment") and auto["keyword"] in user_text:
                                    nome = await get_user_info(sender_id)
                                    # 1. Curtir Comentário
                                    if auto.get("auto_like"): 
                                        await like_comment(comment_id)
                                    # 2. Responder Comentário
                                    await reply_to_comment(comment_id, auto["comment_reply"].replace("{nome}", nome))
                                    # 3. Enviar Direct com Botão
                                    final_dm = auto['dm_text'].replace("{nome}", nome)
                                    await send_dm_with_button(sender_id, final_dm, auto.get("button_title"), auto.get("link_url"))
                                    
                                    auto["count_comments"] += 1
                                    save_db(db)
                                    add_log("system", f"Automação disparada (Comentário): {auto['keyword']}", {"keyword": auto['keyword'], "user": nome})
                                    break
    except Exception as e:
        add_log("error", f"Falha no processamento: {str(e)}")
        import traceback
        traceback.print_exc()
    return {"status": "ok"}

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == os.getenv("INSTAGRAM_VERIFY_TOKEN"):
        return int(params.get("hub.challenge"))
    return "Erro"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
