import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN")

async def diagnose_connection():
    async with httpx.AsyncClient() as client:
        print("\n--- DIAGNÓSTICO DO AGENTE INSTAGRAM ---\n")
        
        # 1. Verificar o Token e as Permissões
        debug_url = f"https://graph.facebook.com/debug_token?input_token={PAGE_ACCESS_TOKEN}&access_token={PAGE_ACCESS_TOKEN}"
        resp_debug = await client.get(debug_url)
        
        if resp_debug.status_code != 200:
            print(f"❌ ERRO NO TOKEN: A Meta não reconheceu seu Token. Verifique o .env")
            print(f"Detalhe: {resp_debug.text}")
            return

        token_data = resp_debug.json().get("data", {})
        scopes = token_data.get("scopes", [])
        print(f"✅ TOKEN VÁLIDO!")
        print(f"🔑 Permissões encontradas: {', '.join(scopes)}")
        
        # Verificar permissões críticas para o bot estilo ManyChat
        required_scopes = ['instagram_manage_messages', 'instagram_manage_comments', 'instagram_basic']
        missing = [s for s in required_scopes if s not in scopes]
        if missing:
            print(f"⚠️ ATENÇÃO: Faltam permissões críticas: {', '.join(missing)}")
        else:
            print(f"🎯 Todas as permissões necessárias estão presentes!")

        # 2. Verificar as Páginas vinculadas
        pages_url = f"https://graph.facebook.com/v21.0/me/accounts?access_token={PAGE_ACCESS_TOKEN}"
        resp_pages = await client.get(pages_url)
        pages_data = resp_pages.json().get("data", [])
        
        if not pages_data:
            print(f"❌ NENHUMA PÁGINA: O Token não tem acesso a nenhuma página do Facebook.")
            return

        print(f"\n📄 Páginas encontradas ({len(pages_data)}):")
        for page in pages_data:
            page_id = page.get('id')
            page_name = page.get('name')
            print(f"   - {page_name} (ID: {page_id})")
            
            # 3. Verificar se a página está inscrita no App (Webhook Ativo)
            sub_url = f"https://graph.facebook.com/v21.0/{page_id}/subscribed_apps?access_token={PAGE_ACCESS_TOKEN}"
            resp_sub = await client.get(sub_url)
            subs = resp_sub.json().get("data", [])
            
            if any(sub.get('link') or True for sub in subs): # Simplificado para checar se há algo
                print(f"   ✅ Webhook: A página está inscrita no seu App!")
            else:
                print(f"   ❌ Webhook: A página NÃO está enviando dados para o App ainda.")

        print("\n--- FIM DO DIAGNÓSTICO ---\n")

if __name__ == "__main__":
    asyncio.run(diagnose_connection())
