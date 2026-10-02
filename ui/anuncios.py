# ==============================================================================
# Google AdSense — tudo DESLIGADO enquanto a variável de ambiente ADSENSE_CLIENT não existir.
# Para ligar (Render → Environment):
#   ADSENSE_CLIENT        = ca-pub-0000000000000000   (código da conta; publica também /ads.txt)
#   ADSENSE_SLOT_FAIXA    = id do bloco entre a configuração e o mapa (página do conversor)
#   ADSENSE_SLOT_LATERAL  = id do bloco abaixo do quadro Layers (página do conversor)
#   ADSENSE_SLOT_CONTEUDO = id do bloco no fim das páginas de texto
# Sem um ADSENSE_SLOT_*, o espaço correspondente simplesmente não aparece.
# ==============================================================================
import os
import re

from nicegui import ui

_PADRAO_CLIENTE = re.compile(r"ca-pub-\d{10,20}")
# identificador fixo do Google no ads.txt (TAG-ID da certificação TAG)
_ADS_TXT_TAG_ID = "f08c47fec0942fa0"


def cliente() -> str | None:
    """Código da conta (ca-pub-...) ou None quando o AdSense está desligado/mal preenchido."""
    valor = os.environ.get("ADSENSE_CLIENT", "").strip()
    return valor if _PADRAO_CLIENTE.fullmatch(valor) else None


def ativo() -> bool:
    return cliente() is not None


def ads_txt() -> str | None:
    """Conteúdo do /ads.txt, ou None (a rota responde 404) quando desligado."""
    c = cliente()
    if c is None:
        return None
    return f"google.com, {c.removeprefix('ca-')}, DIRECT, {_ADS_TXT_TAG_ID}\n"


def html_cabecalho() -> str:
    """Script do AdSense para o <head> (vazio quando desligado)."""
    c = cliente()
    if c is None:
        return ""
    return ('<script async src="https://pagead2.googlesyndication.com/pagead/js/'
            f'adsbygoogle.js?client={c}" crossorigin="anonymous"></script>\n'
            "<script>function cgAnuncios(){document.querySelectorAll("
            "'ins.adsbygoogle:not([data-adsbygoogle-status])').forEach(function(){"
            "(window.adsbygoogle=window.adsbygoogle||[]).push({});});}</script>")


def instalar() -> None:
    """Chamar no início de cada página."""
    cabecalho = html_cabecalho()
    if cabecalho:
        ui.add_head_html(cabecalho)


def espaco(nome: str) -> None:
    """Bloco de anúncio responsivo; só aparece com ADSENSE_CLIENT e ADSENSE_SLOT_<nome>."""
    c = cliente()
    slot = os.environ.get(f"ADSENSE_SLOT_{nome}", "").strip()
    if c is None or not slot.isdigit():
        return
    with ui.element("div").classes("w-full text-center"):
        ui.label("Publicidade").classes("text-caption text-grey-6")
        ui.html(f'<ins class="adsbygoogle" style="display:block" data-ad-client="{c}" '
                f'data-ad-slot="{slot}" data-ad-format="auto" '
                'data-full-width-responsive="true"></ins>',
                sanitize=False).classes("w-full")    # valores validados acima (ca-pub, dígitos)
    # o <ins> é criado pelo Vue depois do carregamento: pede o anúncio quando já existe
    ui.timer(1.0, lambda: ui.run_javascript("window.cgAnuncios && cgAnuncios()"), once=True)
