# ==============================================================================
# Conversor Geo — ponto de entrada (NiceGUI)
# Páginas do site, /health (Render e UptimeRobot), robots.txt, sitemap.xml e ads.txt
# (este último só com o AdSense ligado — ver ui/anuncios.py)
# ==============================================================================
import os

from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from nicegui import app, ui

from ui import anuncios, pagina_principal, paginas_info
from ui.layout import DOMINIO, PAGINAS


# --- Endereço antigo (*.onrender.com) → domínio próprio; /health segue respondendo ---
@app.middleware('http')
async def redirecionar_dominio(request, call_next):
    host = request.headers.get('host', '').split(':')[0].lower()
    if host.endswith('.onrender.com') and request.url.path != '/health':
        destino = f'https://{DOMINIO}{request.url.path}'
        if request.url.query:
            destino += f'?{request.url.query}'
        return RedirectResponse(destino, status_code=301)
    return await call_next(request)


# --- Rota de saúde: leve, não abre página nem cria sessão NiceGUI ---
@app.get('/health')
def health():
    return {'status': 'ok'}


# --- Arquivos para buscadores e AdSense ---
@app.get('/robots.txt', response_class=PlainTextResponse)
def robots():
    return f'User-agent: *\nAllow: /\nSitemap: https://{DOMINIO}/sitemap.xml\n'


@app.get('/sitemap.xml')
def sitemap():
    urls = ''.join(f'<url><loc>https://{DOMINIO}{caminho}</loc></url>' for caminho, _ in PAGINAS)
    return Response('<?xml version="1.0" encoding="UTF-8"?>'
                    f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
                    media_type='application/xml')


@app.get('/ads.txt', response_class=PlainTextResponse)
def ads_txt():
    conteudo = anuncios.ads_txt()       # só existe com ADSENSE_CLIENT definido no Render
    if conteudo is None:
        return PlainTextResponse('Not Found', status_code=404)
    return conteudo


# --- Páginas ---
@ui.page('/')
def pagina_inicial():
    pagina_principal.construir()


paginas_info.registrar()   # /como-usar, /sobre, /privacidade, /contato


if __name__ in {'__main__', '__mp_main__'}:
    from core.leitores.dwg import executavel
    print(f'Entrada DWG: {executavel() or "indisponível (dwg2dxf não encontrado)"}', flush=True)
    ui.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8080)),  # Render define PORT
        title='Conversor Geo — DXF, DWG, KML, Shapefile, SIGEF e TXT',
        language='pt-BR',
        reload=os.environ.get('DEV') == '1',   # DEV=1 só na máquina local
        show=False,
    )
