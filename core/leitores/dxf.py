# ==============================================================================
# Leitor DXF (ezdxf). Entidades do espaço do modelo → feições.
#   POINT/INSERT → ponto · LINE, polilinha aberta, ARC, SPLINE → linha
#   polilinha fechada, CIRCLE, ELLIPSE fechada, HATCH → polígono · TEXT/MTEXT → texto
# ==============================================================================
from __future__ import annotations

import io
import math
from collections import Counter

import numpy as np
import ezdxf
from ezdxf import colors, recover
from ezdxf import path as dxfpath
from ezdxf.math import bulge_center

from core.crs import SistemaRef
from core.leitores import ErroLeitura
from core.leitores._comum import M_POR_GRAU, Bruta, montar_projeto, remover_fechamento
from core.modelo import Camada, Estilo, Projeto, TipoFeicao

PASSO_ARCO_GRAUS = 1.0        # discretização de arcos, círculos e bulges
TOLERANCIA_TEXTO_M = 0.5      # texto a até 0,5 m de um ponto vira rótulo do ponto
ESPESSURA_PADRAO_MM = 0.25


# ------------------------------------------------------------------ estilos
def _rgb_aci(aci: int) -> tuple[int, int, int]:
    """ACI → RGB. A cor 7 (branca no fundo preto do AutoCAD) vira preta: é assim que os
    outros programas (Google Earth, QGIS, impressão) esperam as linhas."""
    if aci == 7 or not 1 <= aci <= 255:
        return (0, 0, 0)
    return tuple(colors.aci2rgb(aci))


def _estilo_layer(layer) -> Estilo:
    if layer.dxf.hasattr("true_color"):
        cor = tuple(colors.int2rgb(layer.dxf.true_color))
    else:
        cor = _rgb_aci(abs(layer.dxf.color))
    lw = layer.dxf.lineweight
    return Estilo(cor, lw / 100 if lw >= 0 else ESPESSURA_PADRAO_MM, layer.dxf.linetype.upper())


def _estilo(e, base: Estilo) -> Estilo:
    """Resolve ByLayer/ByBlock (cor ACI, true color, espessura e tipo de linha)."""
    if e.dxf.hasattr("true_color"):
        cor = tuple(colors.int2rgb(e.dxf.true_color))
    else:
        aci = e.dxf.color
        cor = _rgb_aci(aci) if 1 <= aci <= 255 else base.cor
    lw = e.dxf.lineweight
    if lw >= 0:
        esp = lw / 100
    else:
        esp = base.espessura if lw == -1 else ESPESSURA_PADRAO_MM
    lt = e.dxf.linetype.upper()
    if lt in ("BYLAYER", "BYBLOCK"):
        lt = base.tipo_linha
    return Estilo(cor, esp, lt)


# ------------------------------------------------------------------ geometria
def _para_wcs(e, pts) -> list:
    """Entidades em OCS (LWPOLYLINE, ARC, CIRCLE, TEXT, INSERT) → WCS."""
    ocs = e.ocs()
    if ocs.transform:
        return [tuple(p) for p in ocs.points_to_wcs(pts)]
    return [tuple(float(v) for v in p) for p in pts]


def _arco(cx, cy, r, a_ini_graus, varredura_graus, z) -> list:
    n = max(1, math.ceil(abs(varredura_graus) / PASSO_ARCO_GRAUS))
    ang = np.radians(a_ini_graus + varredura_graus * np.arange(n + 1) / n)
    return [(cx + r * math.cos(a), cy + r * math.sin(a), z) for a in ang]


def _vertices_com_bulge(pts, fechado: bool, z: float) -> list:
    """pts = [(x, y, bulge)]; bulge > 0 é arco anti-horário até o vértice seguinte."""
    saida = []
    n = len(pts)
    for i in range(n if fechado else n - 1):
        x1, y1, b = pts[i]
        x2, y2, _ = pts[(i + 1) % n]
        saida.append((x1, y1, z))
        if abs(b) > 1e-12 and (x1, y1) != (x2, y2):
            c = bulge_center((x1, y1), (x2, y2), b)
            theta = 4.0 * math.atan(b)
            a0 = math.atan2(y1 - c.y, x1 - c.x)
            r = math.hypot(x1 - c.x, y1 - c.y)
            m = max(1, math.ceil(abs(math.degrees(theta)) / PASSO_ARCO_GRAUS))
            for k in range(1, m):
                a = a0 + theta * k / m
                saida.append((c.x + r * math.cos(a), c.y + r * math.sin(a), z))
    if not fechado and n:
        saida.append((pts[-1][0], pts[-1][1], z))
    return saida


def _fechada(pts) -> bool:
    return len(pts) > 2 and math.dist(pts[0][:2], pts[-1][:2]) < 1e-9


# ------------------------------------------------------------------ leitura
def _coletar(msp, camadas: dict[str, Camada], dist_curva: float):
    brutas: list[Bruta] = []
    ignoradas: Counter = Counter()
    P, L, G, T = TipoFeicao.PONTO, TipoFeicao.LINHA, TipoFeicao.POLIGONO, TipoFeicao.TEXTO

    for e in msp:
        t = e.dxftype()
        layer = e.dxf.layer
        cam = camadas.setdefault(layer, Camada(layer))
        est = _estilo(e, cam.estilo)

        def add(tipo, pts, texto=None, atributos=None):
            if tipo == G:
                pts = remover_fechamento(pts)
                if len(pts) < 3:
                    tipo = L
            if tipo == L and len(pts) < 2:
                return
            brutas.append(Bruta(tipo, pts, layer, est, texto, atributos or {}))

        try:
            if t == "POINT":
                add(P, [tuple(e.dxf.location)])
            elif t == "INSERT":
                attrs = {"BLOCO": e.dxf.name}
                attrs.update({a.dxf.tag: a.dxf.text for a in e.attribs})
                add(P, _para_wcs(e, [e.dxf.insert]), atributos=attrs)
            elif t == "TEXT":
                usa_alinh = (e.dxf.halign or e.dxf.valign) and e.dxf.hasattr("align_point")
                p = e.dxf.align_point if usa_alinh else e.dxf.insert
                add(T, _para_wcs(e, [p]), texto=e.plain_text())
            elif t == "MTEXT":
                add(T, [tuple(e.dxf.insert)], texto=e.plain_text())
            elif t == "LINE":
                add(L, [tuple(e.dxf.start), tuple(e.dxf.end)])
            elif t == "LWPOLYLINE":
                v = _vertices_com_bulge(list(e.get_points("xyb")), e.closed, e.dxf.elevation)
                add(G if e.closed else L, _para_wcs(e, v))
            elif t == "POLYLINE":
                if e.is_2d_polyline:
                    pts = [(v.dxf.location.x, v.dxf.location.y, v.dxf.bulge) for v in e.vertices]
                    v = _para_wcs(e, _vertices_com_bulge(pts, e.is_closed, e.dxf.elevation.z))
                elif e.is_3d_polyline:
                    v = [tuple(p) for p in e.points()]
                else:
                    ignoradas["POLYLINE (malha)"] += 1
                    continue
                add(G if e.is_closed else L, v)
            elif t == "ARC":
                varredura = (e.dxf.end_angle - e.dxf.start_angle) % 360 or 360.0
                c = e.dxf.center
                add(L, _para_wcs(e, _arco(c.x, c.y, e.dxf.radius, e.dxf.start_angle, varredura, c.z)))
            elif t == "CIRCLE":
                c = e.dxf.center
                add(G, _para_wcs(e, _arco(c.x, c.y, e.dxf.radius, 0.0, 360.0, c.z)))
            elif t in ("ELLIPSE", "SPLINE"):
                v = [tuple(p) for p in e.flattening(dist_curva)]
                add(G if t == "ELLIPSE" and _fechada(v) else L, v)
            elif t == "HATCH":
                for caminho in dxfpath.from_hatch(e):
                    add(G, [tuple(p) for p in caminho.flattening(dist_curva)])
            else:
                ignoradas[t] += 1
        except Exception:   # entidade corrompida não derruba o arquivo inteiro
            ignoradas[f"{t} (com erro)"] += 1
    return brutas, ignoradas


def _associar_textos(brutas: list[Bruta], tolerancia: float) -> list[Bruta]:
    """Texto a até `tolerancia` do ponto mais próximo vira rótulo desse ponto."""
    pontos = [b for b in brutas if b.tipo == TipoFeicao.PONTO]
    if not pontos:
        return brutas
    xy = np.array([b.pts[0][:2] for b in pontos])
    usados = set()
    for i, b in enumerate(brutas):
        if b.tipo != TipoFeicao.TEXTO or not b.texto:
            continue
        d = np.hypot(xy[:, 0] - b.pts[0][0], xy[:, 1] - b.pts[0][1])
        j = int(np.argmin(d))
        if d[j] <= tolerancia:
            p = pontos[j]
            p.texto = f"{p.texto} / {b.texto}" if p.texto else b.texto
            usados.add(i)
    return [b for i, b in enumerate(brutas) if i not in usados]


def ler_dxf(dados: bytes, sistema: SistemaRef) -> Projeto:
    try:
        doc, _auditor = recover.read(io.BytesIO(dados))
    except (IOError, ezdxf.DXFStructureError) as ex:
        raise ErroLeitura("O arquivo não parece ser um DXF válido. Se veio do AutoCAD, "
                          "salve de novo como DXF (Salvar como → DXF).") from ex

    camadas = {ly.dxf.name: Camada(ly.dxf.name, _estilo_layer(ly),
                                   visivel=ly.is_on() and not ly.is_frozen())
               for ly in doc.layers}
    geo = sistema.tipo == "GEO"
    dist_curva = 0.01 / M_POR_GRAU if geo else 0.01           # flecha máx. de 1 cm
    brutas, ignoradas = _coletar(doc.modelspace(), camadas, dist_curva)
    tol = TOLERANCIA_TEXTO_M / M_POR_GRAU if geo else TOLERANCIA_TEXTO_M
    brutas = _associar_textos(brutas, tol)

    proj = montar_projeto(sistema, brutas, camadas, "DXF")
    if ignoradas:
        lista = ", ".join(f"{k} ({v})" for k, v in ignoradas.most_common())
        proj.avisos.append(f"Entidades não convertidas: {lista}.")
    return proj
