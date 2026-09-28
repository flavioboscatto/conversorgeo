# ==============================================================================
# Leitor da planilha SIGEF/INCRA (.ods) — só as abas perimetro_N.
# A aba "identificacao" (nome, CPF etc.) NÃO é lida.
# Gera: vértices por tipo (VERTICES_M/P/V), segmentos (LIMITES) e a parcela (PERIMETRO).
# ==============================================================================
from __future__ import annotations

import io

from python_calamine import CalamineWorkbook

from core.crs import SistemaRef
from core.geodesia.motor_geodesico import MotorGeodesico
from core.leitores import ErroLeitura
from core.leitores._comum import Bruta, montar_projeto
from core.modelo import Camada, Estilo, Projeto, TipoFeicao

CAMADAS_SIGEF = {
    "VERTICES_M": Estilo((255, 0, 0), 0.25),
    "VERTICES_P": Estilo((255, 255, 0), 0.25),
    "VERTICES_V": Estilo((0, 255, 255), 0.25),
    "LIMITES": Estilo((255, 128, 0), 0.50),
    "PERIMETRO": Estilo((255, 255, 255), 0.35),
}

# colunas da tabela de vértices
C_VERT, C_X, C_SX, C_Y, C_SY, C_H, C_SH, C_MET, C_LIM, C_CNS, C_MAT, C_DESC = range(12)


def _cel(linha: list, j: int):
    return linha[j] if j < len(linha) else ""


def _txt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _num(v, vertice: str, campo: str) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    t = _txt(v).replace(" ", "")
    if not t:
        raise ErroLeitura(f"Vértice {vertice}: campo “{campo}” vazio.")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        raise ErroLeitura(f"Vértice {vertice}: valor “{v}” inválido em “{campo}”.") from None


def _angulo(v, vertice: str, campo: str) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return MotorGeodesico.sexagesimal_para_decimal(_txt(v))
    except ValueError:
        raise ErroLeitura(f"Vértice {vertice}: coordenada “{v}” inválida em “{campo}”.") from None


def _valor_rotulado(linhas: list, rotulo: str) -> str:
    for ln in linhas:
        if _txt(_cel(ln, 0)).startswith(rotulo):
            return _txt(_cel(ln, 1))
    return ""


def _sistema(linhas: list, aba: str) -> SistemaRef:
    for ln in linhas:
        if _txt(_cel(ln, 0)).startswith("Tipo de Coordenada"):
            tipo = _txt(_cel(ln, 1)).lower()
            if "geogr" in tipo or "geod" in tipo:
                return SistemaRef.geografico(gms=True)
            if "utm" in tipo:
                try:
                    mc = _num(_cel(ln, 3), aba, "Meridiano Central")
                    hem = "S" if _txt(_cel(ln, 5)).lower().startswith("s") else "N"
                    return SistemaRef.utm(round((mc + 183.0) / 6.0), hem)
                except ValueError as ex:
                    raise ErroLeitura(f"Aba {aba}: meridiano central/hemisfério inválidos "
                                      f"({ex}).") from None
            raise ErroLeitura(f"Aba {aba}: tipo de coordenada “{tipo}” não reconhecido.")
    raise ErroLeitura(f"Aba {aba}: não encontrei a linha “Tipo de Coordenada”.")


def _linhas_vertices(linhas: list) -> list:
    for i, ln in enumerate(linhas):
        if _txt(_cel(ln, 0)) == "Vértice":
            saida = []
            for ln2 in linhas[i + 1:]:
                if not _txt(_cel(ln2, 0)):
                    break
                saida.append(ln2)
            return saida
    return []


def ler_sigef(dados: bytes) -> Projeto:
    try:
        wb = CalamineWorkbook.from_filelike(io.BytesIO(dados))
    except Exception as ex:
        raise ErroLeitura("Não foi possível abrir a planilha. Confira se é a planilha "
                          ".ods do SIGEF (INCRA).") from ex
    abas = [n for n in wb.sheet_names if n.lower().startswith("perimetro")]
    if not abas:
        raise ErroLeitura("A planilha não tem abas “perimetro_N”. Confira se é a planilha do SIGEF.")

    camadas = {nome: Camada(nome, est) for nome, est in CAMADAS_SIGEF.items()}
    brutas: list[Bruta] = []
    sistema = None
    for aba in abas:
        linhas = wb.get_sheet_by_name(aba).to_python()
        s = _sistema(linhas, aba)
        if sistema is None:
            sistema = s
        elif s != sistema:
            raise ErroLeitura("As abas de perímetro usam sistemas de coordenadas diferentes; "
                              "converta uma de cada vez.")
        vertices = _linhas_vertices(linhas)
        if not vertices:
            continue
        rotulo_x = "E" if s.tipo == "UTM" else "Longitude"
        rotulo_y = "N" if s.tipo == "UTM" else "Latitude"
        pts = []
        for ln in vertices:
            nome = _txt(_cel(ln, C_VERT))
            if s.tipo == "UTM":
                x, y = _num(_cel(ln, C_X), nome, rotulo_x), _num(_cel(ln, C_Y), nome, rotulo_y)
            else:
                x, y = _angulo(_cel(ln, C_X), nome, rotulo_x), _angulo(_cel(ln, C_Y), nome, rotulo_y)
            h = _num(_cel(ln, C_H), nome, "h") if _txt(_cel(ln, C_H)) else 0.0
            pts.append((x, y, h))
            partes = nome.split("-")
            tipo_v = partes[-2].upper() if len(partes) >= 3 else "OUTROS"
            brutas.append(Bruta(TipoFeicao.PONTO, [(x, y, h)], f"VERTICES_{tipo_v}", texto=nome,
                                atributos={
                                    "VERTICE": nome, "PERIMETRO": aba,
                                    "SIGMA_X": _txt(_cel(ln, C_SX)), "SIGMA_Y": _txt(_cel(ln, C_SY)),
                                    "H": _txt(_cel(ln, C_H)), "SIGMA_H": _txt(_cel(ln, C_SH)),
                                    "METODO": _txt(_cel(ln, C_MET)), "LIMITE": _txt(_cel(ln, C_LIM)),
                                }))
        n = len(vertices)
        for i, ln in enumerate(vertices):       # segmento i: vértice i → i+1 (fecha no 1º)
            j = (i + 1) % n
            brutas.append(Bruta(TipoFeicao.LINHA, [pts[i], pts[j]], "LIMITES", atributos={
                "DE": _txt(_cel(ln, C_VERT)), "PARA": _txt(_cel(vertices[j], C_VERT)),
                "LIMITE": _txt(_cel(ln, C_LIM)), "CNS": _txt(_cel(ln, C_CNS)),
                "MATRICULA": _txt(_cel(ln, C_MAT)), "CONFRONT": _txt(_cel(ln, C_DESC)),
                "PERIMETRO": aba,
            }))
        if n >= 3:
            brutas.append(Bruta(TipoFeicao.POLIGONO, pts, "PERIMETRO", atributos={
                "PERIMETRO": aba, "PARCELA": _valor_rotulado(linhas, "Parcela"),
                "LADO": _valor_rotulado(linhas, "Lado"),
            }))

    if sistema is None:
        raise ErroLeitura("Nenhuma aba de perímetro tem vértices preenchidos.")
    return montar_projeto(sistema, brutas, camadas, "SIGEF")
