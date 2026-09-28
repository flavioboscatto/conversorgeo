# ==============================================================================
# Conversor Geo — ponto de entrada (NiceGUI)
# Etapa 0: app mínimo + rota /health para o health check do Render e o pinger externo
# ==============================================================================
import os

from nicegui import app, ui


# --- Rota de saúde: leve, não abre página nem cria sessão NiceGUI ---
@app.get('/health')
def health():
    return {'status': 'ok'}


# --- Página provisória (substituída na Etapa 6) ---
@ui.page('/')
def pagina_inicial():
    ui.label('Conversor Geo — DXF/DWG · KML · Shapefile · SIGEF').classes('text-h5')
    ui.label('Em construção.')


if __name__ in {'__main__', '__mp_main__'}:
    ui.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8080)),  # Render define PORT
        title='Conversor Geo',
        reload=False,
        show=False,
    )
