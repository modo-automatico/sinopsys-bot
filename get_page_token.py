import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

USER_TOKEN = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN")

async def get_real_page_token():
    async with httpx.AsyncClient() as client:
        url = f"https://graph.facebook.com/v21.0/me/accounts?access_token={USER_TOKEN}"
        resp = await client.get(url)
        data = resp.json().get("data", [])
        
        if not data:
            print("Nenhuma página encontrada para este token.")
            return

        for page in data:
            if "Sinopsys Editora" in page['name']:
                print(f"\n✅ TOKEN DE PÁGINA ENCONTRADO PARA: {page['name']}")
                print(f"ID da Página: {page['id']}")
                print(f"Novo Token: {page['access_token']}\n")
                print("--- COPIE O TOKEN ACIMA E SUBSTITUA NO SEU .env ---")

if __name__ == "__main__":
    asyncio.run(get_real_page_token())
