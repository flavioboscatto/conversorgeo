# ==============================================================================
# Conversor Geo — ponto de entrada (NiceGUI)
# Etapa 0: app mínimo + rota /health para o health check do Render e o pinger externo
# ==============================================================================
import os

from nicegui import app, ui

from ui import pagina_principal


# --- Rota de saúde: leve, não abre página nem cria sessão NiceGUI ---
@app.get('/health')
def health():
    return {'status': 'ok'}


# --- Página principal (cresce a cada etapa) ---
@ui.page('/')
def pagina_inicial():
    pagina_principal.construir()


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8080)),  # Render define PORT
        title='Conversor Geo',
        reload=os.environ.get('DEV') == '1',   # DEV=1 só na máquina local
        show=False,
    )
