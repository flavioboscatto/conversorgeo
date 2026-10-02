# ==============================================================================
# Cabeçalho com menu, rodapé e metadados comuns a todas as páginas do site.
# ==============================================================================
from html import escape

from nicegui import ui

from ui import anuncios

COR_TEMA = "#66BB6A"   # verde claro
DOMINIO = "conversorgeo.com.br"
EMAIL_CONTATO = "conversorgeo@gmail.com"

# (caminho, rótulo do menu) — também usado no sitemap.xml
PAGINAS = [("/", "Conversor"), ("/como-usar", "Como usar"), ("/sobre", "Sobre"),
           ("/privacidade", "Privacidade"), ("/contato", "Contato")]


# títulos das páginas de texto: os do Quasar (h1 = 6rem) são grandes demais para leitura
_CSS_TEXTO = """<style>
.cg-texto h1{font-size:1.9rem;line-height:1.25;font-weight:500;margin:0 0 .75rem}
.cg-texto h2{font-size:1.35rem;line-height:1.3;font-weight:500;margin:1.5rem 0 .5rem}
.cg-texto table{border-collapse:collapse;margin:.5rem 0;font-size:.9rem}
.cg-texto th,.cg-texto td{border:1px solid #ddd;padding:.35rem .6rem;vertical-align:top}
.cg-texto th{background:#f1f8e9}
.cg-texto p,.cg-texto li{line-height:1.6}
</style>"""


def preparar(descricao: str) -> None:
    """Início de toda página: tema, descrição para buscadores e AdSense (se ligado)."""
    ui.colors(primary=COR_TEMA)
    ui.add_head_html(f'<meta name="description" content="{escape(descricao)}">')
    ui.add_head_html(_CSS_TEXTO)
    anuncios.instalar()


def cabecalho(atual: str) -> None:
    # fixed=False: no celular o menu ocupa 2 linhas; fixo, roubaria espaço do mapa ao rolar
    with ui.header(fixed=False).classes("items-center text-grey-10 gap-x-6 gap-y-0 flex-wrap"):
        with ui.link(target="/").classes("no-underline text-grey-10"):
            ui.label("Conversor Geo").classes("text-h6")
        ui.label("DXF · KML/KMZ · Shapefile · SIGEF · TXT/CSV").classes("text-caption")
        ui.space()
        with ui.row().classes("gap-x-4 gap-y-0 flex-wrap"):
            for caminho, rotulo in PAGINAS:
                estilo = "text-weight-bold underline" if caminho == atual else "no-underline"
                ui.link(rotulo, caminho).classes(f"text-grey-10 text-body2 {estilo}")


def rodape() -> None:
    with ui.row().classes("w-full max-w-6xl mx-auto px-4 pb-6 pt-2 gap-x-4 gap-y-1 "
                          "items-center flex-wrap text-caption text-grey-7"):
        ui.label("© 2026 Conversor Geo")
        ui.link("Privacidade", "/privacidade").classes("text-grey-7")
        ui.link("Contato", "/contato").classes("text-grey-7")
        ui.label("Os arquivos enviados são processados na memória e não ficam no servidor.")
