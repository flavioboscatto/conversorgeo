# ==============================================================================
# Leitor de TXT/CSV com colunas escolhidas pelo usuário.
# Coordenadas: UTM (E, N), geodésicas decimais ou geodésicas gg,mmss — nas geodésicas,
# sul e oeste com sinal negativo. Coluna de código → layer. Opcionalmente liga os pontos na
# ordem do arquivo, formando linha ou polígono: todos juntos (layer LIGACAO) ou um por código.
# ==============================================================================
from __future__ import annotations

import csv
import re
from dataclasses import dataclass

from core.crs import SistemaRef
from core.leitores import ErroLeitura
from core.leitores._comum import Bruta, montar_projeto, remover_fechamento
from core.modelo import Camada, Estilo, Projeto, TipoFeicao

SEPARADORES = {";": "Ponto e vírgula ( ; )", "\t": "Tabulação", ",": "Vírgula ( , )",
               " ": "Espaço"}
GEOMETRIAS = {"pontos": "Só pontos",
              "linha": "Pontos e linha (na ordem do arquivo)",
              "poligono": "Pontos e polígono (fecha no 1º ponto)"}
LIGACOES = {False: "Na sequência do arquivo (todos os pontos)",
            True: "Na sequência, por código (uma por layer)"}
LAYER_PADRAO = "PONTOS"
LAYER_LIGACAO = "LIGACAO"      # linha/polígono que passa por todos os pontos
COR_LIGACAO = (255, 255, 255)
MAX_LINHAS_ERRO = 3
# cores bem visíveis sobre imagem de satélite, uma por layer na ordem em que aparecem
PALETA = [(255, 255, 0), (255, 0, 0), (0, 255, 255), (255, 0, 255), (255, 128, 0),
          (0, 255, 0), (255, 255, 255), (0, 128, 255), (255, 128, 192), (128, 255, 128)]


@dataclass
class ConfigTxt:
    """Escolhas do usuário. Colunas são índices a partir de 0; None = não usar."""
    separador: str = ";"
    cabecalho: bool = False
    col_x: int = 1                 # E ou longitude
    col_y: int = 2                 # N ou latitude
    col_nome: int | None = 0
    col_z: int | None = None
    col_codigo: int | None = None
    geometria: str = "pontos"      # chave de GEOMETRIAS
    ligar_por_codigo: bool = False  # True: uma linha/polígono por código; só vale com col_codigo


# ------------------------------------------------------------------ texto e colunas
def decodificar(dados: bytes) -> str:
    """UTF-8 (com ou sem BOM); se falhar, Windows-1252 (padrão do Excel/Bloco de Notas antigos)."""
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("cp1252", errors="replace")


def _linhas_uteis(texto: str) -> list[tuple[int, str]]:
    """(número da linha no arquivo, conteúdo) sem linhas vazias nem comentários (#)."""
    saida = []
    for i, ln in enumerate(texto.splitlines(), start=1):
        t = ln.strip()
        if t and not t.startswith("#"):
            saida.append((i, ln))
    return saida


def dividir(linha: str, separador: str) -> list[str]:
    if separador == " ":
        return linha.split()            # vários espaços (ou tabs) contam como um
    return [c.strip() for c in next(csv.reader([linha], delimiter=separador))]


def detectar_separador(texto: str) -> str:
    """Tabulação e ponto e vírgula primeiro; vírgula só quando não sobra outra opção
    (no Brasil a vírgula costuma ser o decimal)."""
    amostra = [ln for _, ln in _linhas_uteis(texto)[:20]]
    if not amostra:
        return ";"
    for sep in ("\t", ";"):
        contagens = {ln.count(sep) for ln in amostra}
        if len(contagens) == 1 and contagens != {0}:
            return sep
    for sep in ("\t", ";"):
        if sum(sep in ln for ln in amostra) >= 0.8 * len(amostra):
            return sep
    # espaço × vírgula: vence o que der mais células numéricas (a vírgula pode ser o decimal)
    def pontos(sep: str) -> int:
        celulas = [dividir(ln, sep) for ln in amostra]
        if min(len(c) for c in celulas) < 2:
            return -1
        return sum(_eh_numero(c) for linha in celulas for c in linha)
    return "," if pontos(",") > pontos(" ") else " "


def _eh_numero(t: str) -> bool:
    try:
        numero(t)
        return True
    except ValueError:
        return False


def detectar_cabecalho(linhas: list[list[str]]) -> bool:
    """Cabeçalho = 1ª linha sem números onde as linhas seguintes têm números."""
    if len(linhas) < 2:
        return False
    num_1 = sum(_eh_numero(c) for c in linhas[0])
    num_2 = sum(_eh_numero(c) for c in linhas[1])
    return num_1 < num_2


def previa(dados: bytes, separador: str, limite: int = 6) -> list[list[str]]:
    texto = decodificar(dados)
    return [dividir(ln, separador) for _, ln in _linhas_uteis(texto)[:limite]]


def sugerir_colunas(linhas: list[list[str]], cabecalho: bool) -> dict:
    """Palpite inicial: pelo nome do cabeçalho; sem cabeçalho, pela ordem
    texto (nome) → números (E, N, h) → texto (código)."""
    sug = {"col_nome": None, "col_x": None, "col_y": None, "col_z": None, "col_codigo": None}
    if not linhas:
        return sug
    if cabecalho:
        nomes = {
            "col_nome": r"^(nome|ponto|pto|pt|id|v[ée]rtice|estaca)$",
            "col_x": r"^(e|x|este|leste|lon|long|longitude|coord_?e)$",
            "col_y": r"^(n|y|norte|lat|latitude|coord_?n)$",
            "col_z": r"^(z|h|cota|alt|altitude|elev|elevacao|elevação|altura)$",
            "col_codigo": r"^(c[óo]d|c[óo]digo|code|desc|descri[çc][ãa]o|layer|camada|obs)$",
        }
        for i, c in enumerate(linhas[0]):
            for chave, padrao in nomes.items():
                if sug[chave] is None and re.match(padrao, c.strip().lower()):
                    sug[chave] = i
        if sug["col_x"] is not None and sug["col_y"] is not None:
            return sug
        sug = dict.fromkeys(sug)
    dados = linhas[1] if cabecalho and len(linhas) > 1 else linhas[0]
    numericas = [i for i, c in enumerate(dados) if _eh_numero(c)]
    textos = [i for i, c in enumerate(dados) if not _eh_numero(c)]
    if len(numericas) >= 2:
        sug["col_x"], sug["col_y"] = numericas[0], numericas[1]
        if len(numericas) >= 3:
            sug["col_z"] = numericas[2]
    antes = [i for i in textos if sug["col_x"] is not None and i < sug["col_x"]]
    depois = [i for i in textos if sug["col_x"] is not None and i > sug["col_x"]]
    if antes:
        sug["col_nome"] = antes[0]
    elif numericas and numericas[0] == 0 and len(numericas) >= 4:
        # nome numérico (1, 2, 3...) antes de E, N, h
        sug["col_nome"], sug["col_x"], sug["col_y"], sug["col_z"] = numericas[:4]
    if depois:
        sug["col_codigo"] = depois[0]
    return sug


# ------------------------------------------------------------------ números e ângulos
def numero(t: str) -> float:
    """Aceita vírgula ou ponto decimal; com os dois, o ponto é separador de milhar."""
    s = t.strip().replace(" ", "")
    if not s:
        raise ValueError("vazio")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"[+-]?(\d+\.?\d*|\.\d+)", s):
        raise ValueError(t)
    return float(s)


def ggmmss_para_decimal(t: str) -> float:
    """gg,mmss (ex.: -27,3543092 = 27°35'43,092" S). Lido como texto, sem arredondar.

    Depois da vírgula: 2 dígitos de minutos, 2 de segundos e o resto é a fração do segundo.
    Faltando dígitos, completa com zeros à direita (48,5 = 48°50'00").
    """
    s = t.strip().replace(" ", "")
    m = re.fullmatch(r"([+-]?)(\d+)(?:[.,](\d*))?", s)
    if not m:
        raise ValueError(t)
    sinal = -1.0 if m.group(1) == "-" else 1.0
    graus = int(m.group(2))
    frac = (m.group(3) or "").ljust(4, "0")
    minutos = int(frac[:2])
    segundos = float(frac[2:4] + "." + (frac[4:] or "0"))
    if minutos >= 60 or segundos >= 60:
        raise ValueError(t)
    return sinal * (graus + minutos / 60.0 + segundos / 3600.0)


# ------------------------------------------------------------------ leitura
def _nome_layer(cod: str) -> str:
    return re.sub(r'[<>/\\":;?*|=`]', "_", cod.strip()) or LAYER_PADRAO


def ler_txt(dados: bytes, sistema: SistemaRef, cfg: ConfigTxt) -> Projeto:
    """`sistema.gms` = True indica coordenadas no formato gg,mmss."""
    if cfg.geometria not in GEOMETRIAS:
        raise ErroLeitura(f"Opção de geometria desconhecida: {cfg.geometria}")
    if cfg.col_x is None or cfg.col_y is None:
        raise ErroLeitura("Escolha as colunas de E/Longitude e N/Latitude.")
    if cfg.col_x == cfg.col_y:
        raise ErroLeitura("E/Longitude e N/Latitude estão apontando para a mesma coluna.")

    linhas = _linhas_uteis(decodificar(dados))
    if cfg.cabecalho:
        linhas = linhas[1:]
    if not linhas:
        raise ErroLeitura("O arquivo não tem linhas de dados.")

    if sistema.tipo == "UTM":
        rot_x, rot_y, conv = "E", "N", numero
    elif sistema.gms:
        rot_x, rot_y, conv = "Longitude", "Latitude", ggmmss_para_decimal
    else:
        rot_x, rot_y, conv = "Longitude", "Latitude", numero

    usadas = [c for c in (cfg.col_x, cfg.col_y, cfg.col_nome, cfg.col_z, cfg.col_codigo)
              if c is not None]
    precisa = max(usadas) + 1
    erros: list[str] = []
    pontos: list[tuple] = []      # (layer, nome, codigo, (x, y, z))
    for num, ln in linhas:
        cel = dividir(ln, cfg.separador)
        if len(cel) < precisa:
            erros.append(f"linha {num}: tem {len(cel)} coluna(s), esperava ao menos {precisa}")
            continue
        try:
            x = conv(cel[cfg.col_x])
        except ValueError:
            erros.append(f"linha {num}: “{cel[cfg.col_x]}” não é {rot_x} válida")
            continue
        try:
            y = conv(cel[cfg.col_y])
        except ValueError:
            erros.append(f"linha {num}: “{cel[cfg.col_y]}” não é {rot_y} válida")
            continue
        z = 0.0
        if cfg.col_z is not None and cel[cfg.col_z].strip():
            try:
                z = numero(cel[cfg.col_z])
            except ValueError:
                erros.append(f"linha {num}: “{cel[cfg.col_z]}” não é uma altitude válida")
                continue
        nome = cel[cfg.col_nome].strip() if cfg.col_nome is not None else ""
        cod = cel[cfg.col_codigo].strip() if cfg.col_codigo is not None else ""
        pontos.append((_nome_layer(cod) if cod else LAYER_PADRAO, nome, cod, (x, y, z)))

    if erros:
        extra = len(erros) - MAX_LINHAS_ERRO
        dica = ""
        if not cfg.cabecalho and erros[0].startswith(f"linha {linhas[0][0]}:"):
            dica = "\nSe a 1ª linha for o cabeçalho, marque “Primeira linha é cabeçalho”."
        raise ErroLeitura(
            f"{len(erros)} linha(s) com problema — confira o separador, as colunas e o formato "
            "das coordenadas:\n" + "\n".join(erros[:MAX_LINHAS_ERRO])
            + (f"\n… e mais {extra}." if extra > 0 else "") + dica)

    camadas: dict[str, Camada] = {}
    brutas: list[Bruta] = []
    grupos: dict[str, list] = {}
    for layer, nome, cod, xyz in pontos:
        if layer not in camadas:
            camadas[layer] = Camada(layer, Estilo(PALETA[len(camadas) % len(PALETA)], 0.35))
        atrib = {"NOME": nome}
        if cfg.col_codigo is not None:
            atrib["CODIGO"] = cod
        brutas.append(Bruta(TipoFeicao.PONTO, [xyz], layer, texto=nome or None, atributos=atrib))
        grupos.setdefault(layer, []).append(xyz)

    avisos = []
    if cfg.geometria != "pontos":
        minimo = 2 if cfg.geometria == "linha" else 3
        tipo = TipoFeicao.LINHA if cfg.geometria == "linha" else TipoFeicao.POLIGONO
        if not (cfg.ligar_por_codigo and cfg.col_codigo is not None):
            # todos os pontos, na ordem do arquivo, num layer próprio
            grupos = {LAYER_LIGACAO: [xyz for *_, xyz in pontos]}
            camadas.setdefault(LAYER_LIGACAO, Camada(LAYER_LIGACAO, Estilo(COR_LIGACAO, 0.35)))
        for layer, pts in grupos.items():
            if tipo == TipoFeicao.POLIGONO:
                pts = remover_fechamento(pts)       # 1º ponto repetido no fim do arquivo
            if len(pts) < minimo:
                avisos.append(f"Layer {layer}: só {len(pts)} ponto(s) — não deu para formar "
                              f"{'a linha' if minimo == 2 else 'o polígono'}.")
                continue
            brutas.append(Bruta(tipo, pts, layer, atributos={"LAYER": layer,
                                                             "PONTOS": str(len(pts))}))

    proj = montar_projeto(sistema, brutas, camadas, "TXT/CSV")
    proj.avisos = avisos + proj.avisos
    return proj
