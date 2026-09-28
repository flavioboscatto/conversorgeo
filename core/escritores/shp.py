# ==============================================================================
# Escritor Shapefile → ZIP com _pontos, _linhas e _poligonos (só os que têm feições),
# Z quando houver, campos LAYER/TIPO/COR/ESPESSURA/TEXTO + atributos (nomes ≤ 10),
# .prj do sistema escolhido e .cpg UTF-8.
# ==============================================================================
from __future__ import annotations

import io
import re
import unicodedata
import zipfile

import numpy as np
import shapefile

from core.crs import SistemaRef, de_geografico, wkt_prj
from core.modelo import Projeto, TipoFeicao

_FIXOS = ["LAYER", "TIPO", "COR", "ESPESSURA", "TEXTO"]


def nome_campo(chave: str, usados: set[str]) -> str:
    """Nome de campo DBF: ASCII maiúsculo, [A-Z0-9_], até 10 caracteres, único."""
    t = unicodedata.normalize("NFKD", str(chave)).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Z0-9_]", "_", t.upper()).strip("_") or "CAMPO"
    if t[0].isdigit():
        t = "C" + t
    base, n = t[:10], 1
    while base in usados:
        sufixo = str(n)
        base, n = t[:10 - len(sufixo)] + sufixo, n + 1
    usados.add(base)
    return base


def _anel_horario(pts: list) -> list:
    anel = pts + [pts[0]]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(anel, anel[1:]))
    return anel[::-1] if area > 0 else anel


def escrever_shp(proj: Projeto, sistema: SistemaRef, nome_base: str) -> bytes:
    grupos = {
        "pontos": [f for f in proj.feicoes if f.tipo in (TipoFeicao.PONTO, TipoFeicao.TEXTO)],
        "linhas": [f for f in proj.feicoes if f.tipo == TipoFeicao.LINHA],
        "poligonos": [f for f in proj.feicoes if f.tipo == TipoFeicao.POLIGONO],
    }
    prj = wkt_prj(sistema)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sufixo, feicoes in grupos.items():
            if not feicoes:
                continue
            tem_z = any(f.tem_z for f in feicoes)
            tipo_shp = {
                "pontos": shapefile.POINTZ if tem_z else shapefile.POINT,
                "linhas": shapefile.POLYLINEZ if tem_z else shapefile.POLYLINE,
                "poligonos": shapefile.POLYGONZ if tem_z else shapefile.POLYGON,
            }[sufixo]
            usados = set(_FIXOS)
            campos: dict[str, str] = {}
            for f in feicoes:
                for k in f.atributos:
                    if k not in campos:
                        campos[k] = nome_campo(k, usados)

            shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
            w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=tipo_shp, encoding="utf-8")
            w.field("LAYER", "C", 80)
            w.field("TIPO", "C", 10)
            w.field("COR", "C", 7)
            w.field("ESPESSURA", "N", 6, 2)
            w.field("TEXTO", "C", 254)
            for nome in campos.values():
                w.field(nome, "C", 254)

            for f in feicoes:
                x, y = de_geografico(sistema, f.coords[:, 0], f.coords[:, 1])
                z = f.coords[:, 2] if f.tem_z else np.zeros(len(x))
                pts = [(float(a), float(b), float(c)) if tem_z else (float(a), float(b))
                       for a, b, c in zip(x, y, z)]
                if sufixo == "pontos":
                    w.pointz(*pts[0]) if tem_z else w.point(*pts[0])
                elif sufixo == "linhas":
                    w.linez([pts]) if tem_z else w.line([pts])
                else:
                    anel = _anel_horario(pts)
                    w.polyz([anel]) if tem_z else w.poly([anel])
                est = proj.estilo_de(f)
                w.record(f.layer[:80], f.tipo.value, "#%02x%02x%02x" % est.cor,
                         round(est.espessura, 2), (f.texto or "")[:254],
                         *[str(f.atributos.get(k, ""))[:254] for k in campos])
            w.close()
            base = f"{nome_base}_{sufixo}"
            zf.writestr(base + ".shp", shp.getvalue())
            zf.writestr(base + ".shx", shx.getvalue())
            zf.writestr(base + ".dbf", dbf.getvalue())
            zf.writestr(base + ".prj", prj)
            zf.writestr(base + ".cpg", "UTF-8")
    return buf.getvalue()
