# ==============================================================================
# Página principal: para cada arquivo, formato → sistema → upload → “Mostrar arquivo na
# imagem” (soma à lista). A saída é sempre um arquivo único com todas as importações.
# Nada é gravado em disco: os arquivos ficam só na memória desta sessão (cada item da lista
# guarda o arquivo original para “Editar importação”, até ser removido ou limpo).
# ==============================================================================
import logging

import numpy as np
from nicegui import run, ui

from core.conversor import (COM_GMS, EXTENSOES, FORMATOS_ENTRADA, FORMATOS_SAIDA,
                            SISTEMA_DO_ARQUIVO, SO_GEODESICOS, escrever, ler, nome_seguro)
from core.crs import FUSOS_SUL, SistemaRef, aviso_fuso, sugerir_fuso, sugerir_hemisferio
from core.leitores import ErroLeitura
from core.leitores.txt import (GEOMETRIAS, LIGACOES, SEPARADORES, ConfigTxt, decodificar,
                               detectar_cabecalho, detectar_separador, previa, sugerir_colunas)
from core.modelo import juntar, recolorir
from ui import anuncios, layout
from ui import mapa as mapa_mod
from ui.mapa import Mapa, cor_hex, hex_para_rgb

log = logging.getLogger(__name__)

TAMANHO_MAX_MB = 10   # o app não se destina a arquivos grandes (RAM do Render Free: 512 MB)

SISTEMAS = {"GEO": "Geodésicas (graus decimais)", "UTM": "UTM"}
SISTEMAS_COM_GMS = {"GEO": "Geodésicas (graus decimais)",
                    "GMS": "Geodésicas (gg,mmss)", "UTM": "UTM"}
NOTAS_ENTRADA = {
    "KML": "KML usa sempre coordenadas geodésicas (WGS 84).",
    "SIGEF": "O sistema é lido da própria planilha (Tipo de Coordenada).",
    "SHP": "O sistema é lido do .prj; o escolhido aqui só vale se o ZIP não tiver .prj.",
    "DXF": "Informe o sistema em que o desenho foi feito.",
    "TXT": "Geodésicas: sul e oeste com sinal negativo (ex.: -27,3543092 = 27°35'43,092\" S). "
           "Depois de enviar, aponte as colunas.",
}
SEM_COLUNA = -1   # opção “—” dos seletores de coluna
NOTAS_SAIDA = {"KML": "KML usa sempre coordenadas geodésicas (WGS 84)."}


class PainelFormatoSistema:
    """Formato primeiro; depois o sistema. Fuso e hemisfério só aparecem quando UTM."""

    def __init__(self, titulo: str, formatos: dict, inicial: str, notas: dict):
        self.notas = notas
        ui.label(titulo).classes("text-subtitle1 text-weight-medium")
        self.formato = ui.select(formatos, value=inicial, label="Formato").classes("w-full")
        self.tipo = ui.select(SISTEMAS, value="UTM", label="Sistema de coordenadas").classes("w-full")
        with ui.row().classes("w-full items-center no-wrap") as self.linha_utm:
            self.fuso = ui.select(list(FUSOS_SUL), value=22, label="Fuso").classes("w-24")
            self.hemisferio = ui.toggle({"S": "Sul", "N": "Norte"}, value="S")
        self.nota = ui.label().classes("text-caption text-grey-8")
        self.tipo.on_value_change(self._atualizar)
        self.formato.on_value_change(self._atualizar)
        self._atualizar()

    def _atualizar(self):
        f = self.formato.value
        opcoes = SISTEMAS_COM_GMS if f in COM_GMS else SISTEMAS
        if set(self.tipo.options) != set(opcoes):
            valor = self.tipo.value if self.tipo.value in opcoes else "GEO"
            self.tipo.set_options(opcoes, value=valor)
        if f in SO_GEODESICOS:
            self.tipo.value = "GEO"
        travado = f in SO_GEODESICOS or f in SISTEMA_DO_ARQUIVO
        self.tipo.set_enabled(not travado)
        self.tipo.set_visibility(f not in SISTEMA_DO_ARQUIVO)
        self.linha_utm.set_visibility(self.tipo.value == "UTM" and f not in SISTEMA_DO_ARQUIVO)
        self.nota.set_text(self.notas.get(f, ""))

    def sistema(self) -> SistemaRef:
        if self.tipo.value == "UTM":
            return SistemaRef.utm(self.fuso.value, self.hemisferio.value)
        return SistemaRef.geografico(gms=self.tipo.value == "GMS")

    def definir_utm(self, fuso: int, hemisferio: str):
        if fuso in FUSOS_SUL:
            self.fuso.value, self.hemisferio.value = fuso, hemisferio

    def definir_sistema(self, s: SistemaRef):
        """Volta a tela para um sistema já usado (Editar importação)."""
        if s.tipo == "UTM":
            self.tipo.value = "UTM"
            self.definir_utm(s.fuso, s.hemisferio)
        else:
            self.tipo.value = "GMS" if s.gms and "GMS" in self.tipo.options else "GEO"


def _resumo_txt(r: dict) -> str:
    return (f"{r['ponto']} pontos · {r['linha']} linhas · "
            f"{r['poligono']} polígonos · {r['texto']} textos")


def construir():
    layout.preparar("Converta levantamentos entre DXF, KML/KMZ e Shapefile, leia a planilha do "
                    "SIGEF e pontos em TXT/CSV, confira sobre imagem de satélite e exporte "
                    "croqui de localização. SIRGAS 2000, geodésicas e UTM.")
    mapa_mod.instalar()
    layout.cabecalho("/")

    # pendente: arquivo recebido e ainda não lido; itens: arquivos já somados à visualização
    # cores: layer → RGB escolhido pelo usuário; ocultas: layers desligadas no painel
    # txt: escolhas do painel de colunas para o TXT/CSV pendente (separador, colunas...)
    # editando: id do item da lista que voltou para a entrada (“Editar importação”)
    estado = {"pendente": None, "itens": [], "combinado": None, "seq": 0,
              "cores": {}, "ocultas": set(), "txt": None, "editando": None}

    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        with ui.card().classes("w-full"):
            with ui.row().classes("w-full gap-8 items-start"):
                with ui.column().classes("flex-1 min-w-[280px]"):
                    entrada = PainelFormatoSistema("Entrada — configuração de cada arquivo",
                                                   FORMATOS_ENTRADA, "DXF", NOTAS_ENTRADA)
                    upload = ui.upload(label=f"Arraste o arquivo aqui ou clique no + "
                                             f"(até {TAMANHO_MAX_MB} MB)",
                                       auto_upload=True, max_files=1,
                                       max_file_size=TAMANHO_MAX_MB * 1024 * 1024) \
                        .props("flat bordered color=primary text-color=grey-10").classes("w-full")
                    recebido = ui.label().classes("text-caption text-grey-8")
                    painel_txt = ui.column().classes("w-full gap-1")
                    painel_txt.set_visibility(False)
                    with ui.row().classes("w-full no-wrap gap-2"):
                        botao_mostrar = ui.button("Mostrar arquivo na imagem", icon="map") \
                            .props("outline").classes("flex-1") \
                            .tooltip("Lê o arquivo com a configuração acima e soma à lista")
                        botao_limpar = ui.button("Limpar importação", icon="delete_sweep") \
                            .props("outline color=negative").classes("flex-1") \
                            .tooltip("Remove todos os arquivos importados")
                    botao_cancelar = ui.button("Cancelar edição", icon="undo") \
                        .props("flat dense color=grey-8").classes("self-end") \
                        .tooltip("Mantém o arquivo como estava na imagem")
                    botao_cancelar.set_visibility(False)
                    botao_mostrar.disable()
                    botao_limpar.disable()
                    ui.label("Arquivos importados").classes("text-subtitle2 q-mt-sm")
                    lista = ui.column().classes("w-full gap-1")
                with ui.column().classes("flex-1 min-w-[280px]"):
                    saida = PainelFormatoSistema("Saída — arquivo único", FORMATOS_SAIDA, "KML",
                                                 NOTAS_SAIDA)
                    kmz = ui.toggle({True: "KMZ (com ícones)", False: "KML"}, value=True)
                    botao = ui.button("Converter e baixar", icon="download") \
                        .props("text-color=grey-10").classes("w-full")
            status = ui.label().classes("text-body2")
            avisos = ui.label().classes("text-orange-10 text-weight-medium whitespace-pre-line")
            erro = ui.label().classes("text-negative text-weight-medium whitespace-pre-line")

        anuncios.espaco("FAIXA")           # só aparece com o AdSense ligado no Render
        with ui.row().classes("w-full gap-4 items-start no-wrap max-md:flex-wrap"):
            with ui.card().classes("flex-1 min-w-[300px] p-1"):
                mapa = Mapa()
            with ui.column().classes("w-64 max-md:w-full gap-4"):
                with ui.card().classes("w-full"):
                    ui.label("Imagem").classes("text-subtitle1 text-weight-medium")
                    ui.label("Imagem de fundo").classes("text-caption text-grey-8")
                    fundo = ui.radio({"esri": "Esri (atual)",
                                      "sc": "Ortofoto SC 2012 (só SC)"},
                                     value="esri").props("dense")
                    ui.label("Rótulos").classes("text-caption text-grey-8")
                    rotulos = ui.radio({"nenhum": "Sem rótulos",
                                        "esri": "Esri (ruas e lugares)",
                                        "osm": "OpenStreetMap (só nomes de ruas)"},
                                       value="nenhum").props("dense")
                    formato_img = ui.toggle({"png": "PNG", "jpg": "JPG"}, value="png") \
                        .props("dense")
                    botao_img = ui.button("Exportar imagem", icon="image") \
                        .props("text-color=grey-10").classes("w-full") \
                        .tooltip("Salva a vista atual do mapa com as layers habilitadas")
                    ui.label("Enquadre o mapa como quiser antes de exportar.") \
                        .classes("text-caption text-grey-7")
                with ui.card().classes("w-full"):
                    ui.label("Layers").classes("text-subtitle1 text-weight-medium")
                    ui.label("Clique no quadrado para trocar a cor (vale também para as saídas).") \
                        .classes("text-caption text-grey-7")
                    painel_layers = ui.column().classes("gap-0")
                anuncios.espaco("LATERAL")
    layout.rodape()

    kmz.bind_visibility_from(saida.formato, "value", backward=lambda v: v == "KML")

    # ------------------------------------------------------------------ exibição
    def limpar_mensagens():
        erro.set_text("")
        avisos.set_text("")

    def ajustar_upload():
        upload.props(f"accept={EXTENSOES[entrada.formato.value]}")

    def ajustar_botoes():
        botao_mostrar.set_enabled(estado["pendente"] is not None)
        botao_mostrar.set_text("Atualizar na imagem" if estado["editando"]
                               else "Mostrar arquivo na imagem")
        botao_limpar.set_enabled(bool(estado["itens"]) or estado["pendente"] is not None)
        botao_cancelar.set_visibility(estado["editando"] is not None)

    def mostrar_lista():
        lista.clear()
        with lista:
            if not estado["itens"]:
                ui.label("Nenhum arquivo importado.").classes("text-caption text-grey-7")
            for it in estado["itens"]:
                with ui.row().classes("w-full items-center no-wrap gap-2 q-pa-xs rounded-borders") \
                        .style("background:#f1f8e9"):
                    ui.icon("description", color="green-8")
                    with ui.column().classes("gap-0 flex-1 min-w-0"):
                        ui.label(it["nome"]).classes("text-body2 text-weight-medium ellipsis")
                        ui.label(f"{FORMATOS_ENTRADA[it['formato']]} · {it['sistema']} · "
                                 f"{_resumo_txt(it['proj'].resumo())}") \
                            .classes("text-caption text-grey-8")
                    if it["id"] == estado["editando"]:
                        ui.badge("em edição", color="orange-8")
                    else:
                        ui.button(icon="edit", on_click=lambda _, i=it["id"]: editar(i)) \
                            .props("flat round dense color=grey-8") \
                            .tooltip("Editar importação: muda sistema, colunas ou geometria")
                    ui.button(icon="close", on_click=lambda _, i=it["id"]: remover(i)) \
                        .props("flat round dense color=negative").tooltip("Remover este arquivo")

    def mostrar_layers(proj):
        painel_layers.clear()
        with painel_layers:
            if proj is None:
                ui.label("Envie um arquivo para ver as layers.").classes("text-caption text-grey-7")
                return
            contagem = {}
            for f in proj.feicoes:
                contagem[f.layer] = contagem.get(f.layer, 0) + 1
            for nome, n in contagem.items():
                cor = cor_hex(proj.camadas[nome].estilo.cor)
                with ui.row().classes("items-center no-wrap gap-1"):
                    with ui.button().props("dense unelevated size=xs") \
                            .style(f"background:{cor} !important;min-width:16px;min-height:16px;"
                                   "border:1px solid #333").tooltip("Trocar cor"):
                        ui.color_picker(on_pick=lambda e, n=nome: trocar_cor(n, e.color))
                    ui.checkbox(f"{nome} ({n})", value=nome not in estado["ocultas"],
                                on_change=lambda e, n=nome: alternar_layer(n, e.value)) \
                        .props("dense")

    def preparar_txt(dados: bytes, separador: str | None = None, cabecalho: bool | None = None):
        """Detecta separador/cabeçalho (se não informados), sugere as colunas e mostra o painel."""
        sep = separador if separador is not None else detectar_separador(decodificar(dados))
        linhas = previa(dados, sep)
        cab = cabecalho if cabecalho is not None else detectar_cabecalho(linhas)
        sug = sugerir_colunas(linhas, cab)
        anterior = estado["txt"] or {}
        estado["txt"] = {"separador": sep, "cabecalho": cab,
                         "geometria": anterior.get("geometria", "pontos"),
                         "ligar_por_codigo": anterior.get("ligar_por_codigo", False),
                         **{k: SEM_COLUNA if v is None else v for k, v in sug.items()}}
        mostrar_painel_txt(linhas)

    def mostrar_painel_txt(linhas: list[list[str]]):
        cfg = estado["txt"]
        painel_txt.clear()
        painel_txt.set_visibility(True)
        n_col = max((len(ln) for ln in linhas), default=0)
        titulos = linhas[0] if cfg["cabecalho"] and linhas else []
        dados_prev = linhas[1:] if cfg["cabecalho"] else linhas
        nomes = [f"{i + 1}" + (f": {titulos[i]}" if i < len(titulos) and titulos[i] else "")
                 for i in range(n_col)]
        opcoes = {SEM_COLUNA: "—", **dict(enumerate(nomes))}
        with painel_txt:
            ui.label("Colunas do arquivo").classes("text-subtitle2")
            with ui.row().classes("w-full items-center no-wrap gap-2"):
                ui.select(SEPARADORES, value=cfg["separador"], label="Separador",
                          on_change=lambda e: preparar_txt(estado["pendente"]["dados"],
                                                           e.value, None)) \
                    .classes("flex-1").props("dense")
                ui.checkbox("Primeira linha é cabeçalho", value=cfg["cabecalho"],
                            on_change=lambda e: preparar_txt(estado["pendente"]["dados"],
                                                             cfg["separador"], e.value)) \
                    .props("dense")
            colunas = [{"name": f"c{i}", "label": nomes[i], "field": f"c{i}", "align": "left"}
                       for i in range(n_col)]
            linhas_tab = [{f"c{i}": (ln[i] if i < len(ln) else "") for i in range(n_col)}
                          for ln in dados_prev[:5]]
            with ui.element("div").classes("w-full overflow-x-auto"):
                ui.table(columns=colunas, rows=linhas_tab).props("dense flat bordered") \
                    .classes("text-caption")

            def alterar(chave, valor):
                cfg[chave] = valor
                # “Ligar os pontos” só faz sentido com linha/polígono e coluna de código
                bloco_ligacao.set_visibility(cfg["geometria"] != "pontos"
                                             and cfg["col_codigo"] != SEM_COLUNA)

            with ui.grid(columns=2).classes("w-full gap-x-2 gap-y-0"):
                for chave, rotulo in (("col_x", "E / Longitude *"), ("col_y", "N / Latitude *"),
                                      ("col_nome", "Nome do ponto"), ("col_z", "h / Z"),
                                      ("col_codigo", "Código → layer")):
                    if cfg[chave] not in opcoes:
                        cfg[chave] = SEM_COLUNA
                    ui.select(opcoes, value=cfg[chave], label=rotulo,
                              on_change=lambda e, k=chave: alterar(k, e.value)).props("dense")
            ui.radio(GEOMETRIAS, value=cfg["geometria"],
                     on_change=lambda e: alterar("geometria", e.value)) \
                .props("dense").classes("text-body2")
            with ui.column().classes("w-full gap-0 q-pl-md") as bloco_ligacao:
                ui.label("Ligar os pontos").classes("text-caption text-grey-8")
                ui.radio(LIGACOES, value=cfg["ligar_por_codigo"],
                         on_change=lambda e: alterar("ligar_por_codigo", e.value)) \
                    .props("dense").classes("text-body2")
            alterar("geometria", cfg["geometria"])
            ui.label("Cada código vira uma layer. Ligando todos os pontos, a linha/polígono "
                     "fica na layer LIGACAO.").classes("text-caption text-grey-7")

    def esconder_painel_txt():
        estado["txt"] = None
        painel_txt.clear()
        painel_txt.set_visibility(False)

    def config_txt() -> ConfigTxt:
        cfg = estado["txt"]
        col = {k: (None if cfg[k] == SEM_COLUNA else cfg[k])
               for k in ("col_x", "col_y", "col_nome", "col_z", "col_codigo")}
        return ConfigTxt(cfg["separador"], cfg["cabecalho"], geometria=cfg["geometria"],
                         ligar_por_codigo=cfg["ligar_por_codigo"], **col)

    def sugerir_saida(proj):
        itens = estado["itens"]
        if len(itens) == 1 and itens[0]["proj"].crs_origem.tipo == "UTM":
            s = itens[0]["proj"].crs_origem
            saida.definir_utm(s.fuso, s.hemisferio)
            return
        lon = np.concatenate([f.coords[:, 0] for f in proj.feicoes])
        lat = np.concatenate([f.coords[:, 1] for f in proj.feicoes])
        saida.definir_utm(sugerir_fuso(float(np.median(lon))),
                          sugerir_hemisferio(float(np.median(lat))))

    async def atualizar_visao(enquadrar: bool = True):
        """Junta os arquivos da lista, aplica as cores escolhidas e redesenha tudo."""
        mostrar_lista()
        ajustar_botoes()
        if not estado["itens"]:
            estado["combinado"] = None
            mapa.limpar()
            mostrar_layers(None)
            status.set_text("")
            avisos.set_text("")
            return
        proj = juntar([(it["prefixo"], it["proj"]) for it in estado["itens"]])
        for nome, cor in estado["cores"].items():
            if nome in proj.camadas:
                recolorir(proj, nome, cor)
        estado["combinado"] = proj
        n = len(estado["itens"])
        status.set_text(f"{n} arquivo{'s' if n > 1 else ''} na visualização — "
                        f"{_resumo_txt(proj.resumo())}")
        avisos.set_text("\n".join(proj.avisos))
        if enquadrar:
            sugerir_saida(proj)
        # mapa antes do painel: redesenhar o painel apaga o seletor de cor que chamou isto
        await mapa.mostrar(proj, enquadrar=enquadrar, ocultas=estado["ocultas"])
        mostrar_layers(proj)

    async def trocar_cor(nome: str, cor_txt: str):
        cor = hex_para_rgb(cor_txt)
        if cor is None:
            return
        estado["cores"][nome] = cor
        await atualizar_visao(enquadrar=False)      # mantém o enquadramento do usuário

    def alternar_layer(nome: str, visivel: bool):
        (estado["ocultas"].discard if visivel else estado["ocultas"].add)(nome)
        mapa.alternar(nome, visivel)

    async def exportar_imagem():
        if estado["combinado"] is None:
            ui.notify("Importe ao menos um arquivo antes de exportar a imagem.", type="warning")
            return
        itens = estado["itens"]
        base = nome_seguro(itens[0]["nome"]) if len(itens) == 1 else "combinado"
        nome = f"{base}_croqui.{formato_img.value}"
        resultado = await mapa.exportar_imagem(formato_img.value, nome)
        if resultado == "ok":
            ui.notify(f"{nome} gerado.", type="positive")
        else:
            log.error("Falha ao exportar imagem: %s", resultado)
            ui.notify("Não foi possível gerar a imagem. Aguarde a imagem de fundo carregar "
                      "por completo e tente de novo.", type="negative")

    # ------------------------------------------------------------------ ações
    async def ao_enviar(e):
        """Só recebe o arquivo; a leitura acontece em “Mostrar arquivo na imagem”."""
        if estado["editando"] is not None:      # arquivo novo durante a edição: vira importação nova
            estado["editando"] = None
            mostrar_lista()
        estado["pendente"] = {"dados": await e.file.read(), "nome": e.file.name,
                              "formato": entrada.formato.value}
        upload.reset()
        limpar_mensagens()
        n_bytes = len(estado["pendente"]["dados"])
        tamanho = ("menos de 1" if n_bytes < 1024
                   else f"{n_bytes / 1024:,.0f}".replace(",", "."))
        recebido.set_text(f"Arquivo recebido: {e.file.name} ({tamanho} kB) — confira o "
                          "sistema e clique em “Mostrar arquivo na imagem”.")
        if estado["pendente"]["formato"] == "TXT":
            preparar_txt(estado["pendente"]["dados"])
        else:
            esconder_painel_txt()
        ajustar_botoes()

    async def mostrar_arquivo() -> bool:
        """Lê o arquivo pendente com a configuração atual e soma à lista
        (ou substitui o item que está em edição)."""
        limpar_mensagens()
        pend = estado["pendente"]
        if pend is None:
            return False
        sistema = entrada.sistema()
        try:
            cfg = config_txt() if pend["formato"] == "TXT" else None
            proj = await run.io_bound(ler, pend["formato"], pend["dados"], sistema, cfg)
        except ErroLeitura as ex:
            erro.set_text(f"{pend['nome']}: {ex}")
            return False
        except Exception:
            log.exception("Falha ao ler %s", pend["nome"])
            erro.set_text(f"{pend['nome']}: não foi possível ler o arquivo. Confira se o "
                          "formato escolhido corresponde ao arquivo enviado.")
            return False
        # o arquivo e as escolhas ficam guardados no item (só na memória) para “Editar”
        item = {"nome": pend["nome"], "prefixo": nome_seguro(pend["nome"]),
                "formato": pend["formato"], "sistema": proj.crs_origem.descricao, "proj": proj,
                "dados": pend["dados"], "sistema_tela": sistema,
                "txt": dict(estado["txt"]) if estado["txt"] else None}
        editando = estado["editando"]
        if editando is not None and any(it["id"] == editando for it in estado["itens"]):
            item["id"] = editando
            estado["itens"] = [item if it["id"] == editando else it for it in estado["itens"]]
        else:
            estado["seq"] += 1
            item["id"] = estado["seq"]
            estado["itens"].append(item)
        estado["editando"] = None
        estado["pendente"] = None
        recebido.set_text("")
        esconder_painel_txt()
        await atualizar_visao()
        return True

    def editar(ident: int):
        """Volta o arquivo da lista para a entrada, com o formato, o sistema e as colunas usados."""
        it = next((i for i in estado["itens"] if i["id"] == ident), None)
        if it is None:
            return
        limpar_mensagens()
        estado["editando"] = None           # troca de formato abaixo não deve cancelar nada
        entrada.formato.value = it["formato"]
        entrada.definir_sistema(it["sistema_tela"])
        estado["pendente"] = {"dados": it["dados"], "nome": it["nome"], "formato": it["formato"]}
        estado["editando"] = ident
        if it["formato"] == "TXT" and it["txt"]:
            estado["txt"] = dict(it["txt"])
            mostrar_painel_txt(previa(it["dados"], it["txt"]["separador"]))
        else:
            esconder_painel_txt()
        recebido.set_text(f"Editando {it['nome']} — altere o que precisar e clique em "
                          "“Atualizar na imagem”.")
        mostrar_lista()
        ajustar_botoes()

    def cancelar_edicao():
        estado["editando"] = None
        estado["pendente"] = None
        recebido.set_text("")
        esconder_painel_txt()
        limpar_mensagens()
        mostrar_lista()
        ajustar_botoes()

    async def remover(ident: int):
        estado["itens"] = [it for it in estado["itens"] if it["id"] != ident]
        if estado["editando"] == ident:
            cancelar_edicao()
        limpar_mensagens()
        await atualizar_visao()

    async def limpar_importacao():
        estado["editando"] = None
        estado["pendente"] = None
        estado["itens"] = []
        estado["cores"] = {}
        estado["ocultas"] = set()
        upload.reset()
        recebido.set_text("")
        esconder_painel_txt()
        limpar_mensagens()
        await atualizar_visao()
        ui.notify("Importações descartadas.")

    def ao_mudar_formato_entrada():
        ajustar_upload()
        pend = estado["pendente"]
        if pend is not None and pend["formato"] != entrada.formato.value:
            estado["pendente"] = None
            if estado["editando"] is not None:
                estado["editando"] = None
                mostrar_lista()
            esconder_painel_txt()
            recebido.set_text(f"Formato alterado — envie um arquivo "
                              f"{FORMATOS_ENTRADA[entrada.formato.value]}.")
            ajustar_botoes()

    async def converter():
        limpar_mensagens()
        if estado["pendente"] is not None and not await mostrar_arquivo():
            return                     # arquivo recebido e ainda não mostrado entra também
        proj = estado["combinado"]
        if proj is None:
            erro.set_text("Envie um arquivo de entrada primeiro.")
            return
        s = saida.sistema()
        lon = np.concatenate([f.coords[:, 0] for f in proj.feicoes])
        aviso = aviso_fuso(s, lon)
        itens = estado["itens"]
        nome_base = itens[0]["nome"] if len(itens) == 1 else "combinado"
        try:
            dados, nome = await run.io_bound(escrever, proj, saida.formato.value, s,
                                             nome_base, bool(kmz.value))
        except Exception:
            log.exception("Falha ao gravar %s", saida.formato.value)
            erro.set_text("Não foi possível gerar o arquivo de saída.")
            return
        ui.download.content(dados, nome)
        avisos.set_text("\n".join(proj.avisos + ([aviso] if aviso else [])))
        ui.notify(f"{nome} gerado com {len(itens)} arquivo(s) "
                  f"({len(dados) / 1024:,.0f} kB).".replace(",", "."), type="positive")

    upload.on_upload(ao_enviar)
    upload.on_rejected(lambda: ui.notify(f"Arquivo maior que {TAMANHO_MAX_MB} MB.", type="negative"))
    entrada.formato.on_value_change(ao_mudar_formato_entrada)
    botao.on_click(converter)
    botao_mostrar.on_click(mostrar_arquivo)
    botao_limpar.on_click(limpar_importacao)
    botao_cancelar.on_click(cancelar_edicao)
    botao_img.on_click(exportar_imagem)
    rotulos.on_value_change(lambda e: mapa.rotulos(e.value))
    fundo.on_value_change(lambda e: mapa.fundo(e.value))
    ajustar_upload()
    mostrar_lista()
    mostrar_layers(None)
