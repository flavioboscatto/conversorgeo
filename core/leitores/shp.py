# ==============================================================================
# Leitor Shapefile em ZIP (pyshp). Aceita vários shapefiles no mesmo ZIP.
# Sistema: lido do .prj; sem .prj, usa o sistema informado pelo usuário.
# Layer: campo LAYER (se existir) ou o nome do shapefile. COR/TEXTO/ESPESSURA
# (gravados pelo nosso escritor) voltam como estilo e rótulo.
# ==============================================================================
from __future__ import annotations

import io
import posixpath
import zipfile

import shapefile

from core.crs import SistemaRef, sistema_de_prj
from core.leitores import ErroLeitura
from core.leitores._comum import Bruta, montar_projeto, remover_fechamento
from core.modelo import Camada, Estilo, Projeto, TipoFeicao

_CAMPOS_ESTILO = {"LAYER", "TIPO", "COR", "ESPESSURA", "TEXTO"}


def _cor_hex(v) -> tuple[int, int, int] | None:
    t = str(v or "").strip().lstrip("#")
    if len(t) == 6:
        try:
            return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)
        except ValueError:
            return None
    return None


def _area_assinada(anel) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1, *_), (x2, y2, *_) in zip(anel, anel[1:] + anel[:1])) / 2


def _arquivos(dados: bytes) -> dict[str, dict[str, bytes]]:
    """{nome_base: {'.shp': bytes, '.dbf': ..., '.shx': ..., '.prj': ..., '.cpg': ...}}"""
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise ErroLeitura("Envie o shapefile compactado em ZIP (com .shp, .shx, .dbf e .prj).") from None
    grupos: dict[str, dict[str, bytes]] = {}
    with z:
        for nome in z.namelist():
            base, ext = posixpath.splitext(nome)
            ext = ext.lower()
            if ext in (".shp", ".shx", ".dbf", ".prj", ".cpg") and "__MACOSX" not in nome:
                grupos.setdefault(base, {})[ext] = z.read(nome)
    grupos = {b: g for b, g in grupos.items() if ".shp" in g}
    if not grupos:
        raise ErroLeitura("O ZIP não contém nenhum arquivo .shp.")
    for base, g in grupos.items():
        if ".dbf" not in g:
            raise ErroLeitura(f"Falta o arquivo {posixpath.basename(base)}.dbf dentro do ZIP.")
    return grupos


def ler_shp(dados: bytes, sistema_informado: SistemaRef) -> Projeto:
    grupos = _arquivos(dados)
    avisos = []
    sistema = None
    brutas: list[Bruta] = []
    camadas: dict[str, Camada] = {}

    for base, g in sorted(grupos.items()):
        nome_shp = posixpath.basename(base)
        if ".prj" in g:
            try:
                s, aviso = sistema_de_prj(g[".prj"].decode("utf-8", "replace"))
            except ValueError as ex:
                raise ErroLeitura(f"{nome_shp}.prj: {ex}") from None
            if aviso:
                avisos.append(aviso)
        else:
            s = sistema_informado
            avisos.append(f"{nome_shp} não tem .prj; usado o sistema informado "
                          f"({sistema_informado.descricao}).")
        if sistema is None:
            sistema = s
        elif s != sistema:
            raise ErroLeitura("Os shapefiles do ZIP estão em sistemas diferentes; "
                              "envie um sistema por vez.")

        cpg = g.get(".cpg", b"").decode("ascii", "ignore").strip()
        encoding = "utf-8" if not cpg or "UTF" in cpg.upper() or cpg == "65001" else "latin-1"
        try:
            r = shapefile.Reader(shp=io.BytesIO(g[".shp"]), dbf=io.BytesIO(g[".dbf"]),
                                 shx=io.BytesIO(g[".shx"]) if ".shx" in g else None,
                                 encoding=encoding, encodingErrors="replace")
            nomes = [f[0] for f in r.fields[1:]]
            chave_layer = next((n for n in nomes if n.upper() == "LAYER"), None)
            for sr in r.iterShapeRecords():
                shp, rec = sr.shape, sr.record.as_dict()
                layer = str(rec.get(chave_layer) or nome_shp) if chave_layer else nome_shp
                cor = _cor_hex(rec.get("COR"))
                esp = rec.get("ESPESSURA")
                est = Estilo(cor or (255, 255, 255), float(esp) if esp else 1.0) if (cor or esp) else None
                texto = str(rec.get("TEXTO") or "") or None
                attrs = {k: ("" if v is None else str(v)) for k, v in rec.items()
                         if k.upper() not in _CAMPOS_ESTILO}
                if est and layer not in camadas:
                    camadas[layer] = Camada(layer, est)
                pts = shp.points
                if not pts:
                    continue
                zs = list(getattr(shp, "z", []) or []) or [0.0] * len(pts)
                xyz = [(p[0], p[1], zs[i] if i < len(zs) else 0.0) for i, p in enumerate(pts)]
                base_tipo = shp.shapeType % 10          # 1 ponto, 3 linha, 5 polígono, 8 multiponto
                if base_tipo in (1, 8):
                    tipo = TipoFeicao.TEXTO if str(rec.get("TIPO", "")).lower() == "texto" \
                        else TipoFeicao.PONTO
                    for p in xyz:
                        brutas.append(Bruta(tipo, [p], layer, est, texto, attrs))
                    continue
                partes = list(shp.parts) + [len(xyz)]
                for a, b in zip(partes[:-1], partes[1:]):
                    trecho = xyz[a:b]
                    if base_tipo == 3:
                        brutas.append(Bruta(TipoFeicao.LINHA, trecho, layer, est, texto, attrs))
                    elif base_tipo == 5 and (len(partes) == 2 or _area_assinada(trecho) <= 0):
                        # anel externo = horário; furos (anti-horário) são ignorados
                        brutas.append(Bruta(TipoFeicao.POLIGONO, remover_fechamento(trecho),
                                            layer, est, texto, attrs))
        except shapefile.ShapefileException as ex:
            raise ErroLeitura(f"Não foi possível ler {nome_shp}.shp ({ex}).") from None

    proj = montar_projeto(sistema, brutas, camadas, "Shapefile")
    proj.avisos[:0] = avisos
    return proj
