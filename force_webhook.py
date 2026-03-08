import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN")

async def force_subscribe_full():
    async with httpx.AsyncClient() as client:
        # Tenta assinar os campos de mensagens e comentários separadamente se necessário
        url = f"https://graph.facebook.com/v21.0/me/subscribed_apps?access_token={PAGE_ACCESS_TOKEN}"
        
        # Tentativa 1: Campos básicos de mensagens (Página)
        payload_page = {
            "subscribed_fields": "messages,messaging_postbacks,messaging_optins"
        }
        
        print("Tentando assinar campos de Mensagens (Direct)...")
        resp1 = await client.post(url, data=payload_page)
        print(f"Resposta Mensagens: {resp1.status_code} - {resp1.text}")

        # Tentativa 2: Campos de Feed/Comentários (Página/IG)
        # Nota: O campo 'feed' na página muitas vezes traz os comentários do IG vinculado
        payload_feed = {
            "subscribed_fields": "feed"
        }
        print("\nTentando assinar campo de Feed (Comentários)...")
        resp2 = await client.post(url, data=payload_feed)
        print(f"Resposta Feed: {resp2.status_code} - {resp2.text}")

if __name__ == "__main__":
    asyncio.run(force_subscribe_full())
