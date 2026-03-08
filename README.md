# Agente Inteligente para Instagram (Estilo ManyChat)

Este projeto é um servidor de Webhook que utiliza a API do Gemini para responder automaticamente a comentários e DMs no Instagram.

## Funcionalidades
- **Resposta a Comentários:** Identifica novos comentários e responde de forma inteligente.
- **Respostas via DM:** Conversa com usuários através do Direct.
- **Integração Gemini:** Respostas humanas e contextuais usando o modelo `gemini-2.0-flash`.

## Pré-requisitos
1. **Python 3.10+**
2. **Ngrok:** Para expor seu servidor local para a internet (necessário para o Webhook do Meta).
3. **Meta App:**
   - Crie um app no [Meta for Developers](https://developers.facebook.com/).
   - Adicione o produto "Instagram Graph API".
   - Configure o Webhook para os campos `comments` e `messages`.
   - Obtenha um **Page Access Token** com as permissões: `instagram_basic`, `instagram_manage_comments`, `instagram_manage_messages`, `pages_manage_metadata`, `pages_show_list`.

## Como Executar
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure o arquivo `.env` com suas chaves.
3. Inicie o servidor:
   ```bash
   python main.py
   ```
4. Em outro terminal, inicie o Ngrok:
   ```bash
   ngrok http 8000
   ```
5. No painel do Meta, configure a URL do Webhook como: `https://seu-endereco-ngrok.app/webhook`.

## Sobre Novos Seguidores
O envio de DM para quem começou a seguir requer que o Webhook do campo `follows` esteja ativo. Note que o Meta impõe restrições rigorosas sobre automação de primeiro contato para evitar SPAM. Certifique-se de que seu App tenha as permissões aprovadas para produção.

## Próximos Passos
- Implementar banco de dados para salvar histórico de conversas (memória).
- Adicionar suporte a imagens e áudio (Multimodal).
- Painel de controle para monitorar as interações.
