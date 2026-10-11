# Shopee Video Publisher

Sistema web para automação de publicação de vídeos de afiliado na Shopee Video,
usando a API oficial da Shopee Open Platform (Video Management).

## Funcionalidades
- Login com usuário/senha
- Conexão OAuth com conta de afiliado Shopee (`auth_type=user`)
- Upload de vídeo (MediaSpace API: init → partes → complete)
- Vinculação de até 6 produtos por vídeo
- Publicação via `v2.video/post_video`
- Listagem e métricas de vídeos

## Configuração
Variáveis de ambiente:
- `SECRET_KEY` — chave de sessão Flask
- `APP_USER` / `APP_PASS` — credenciais de login (padrão: demo/demo123)
- `SHOPEE_PARTNER_ID` / `SHOPEE_PARTNER_KEY` — credenciais do app (após aprovação)
- `SHOPEE_REGION` — `BR` (padrão)
- `SHOPEE_REDIRECT_URI` — URL de callback OAuth

## Rodar local
```
pip install -r requirements.txt
python app.py
```
