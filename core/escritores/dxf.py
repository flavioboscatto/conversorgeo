# ==============================================================================
# Escritor DXF (R2018, ezdxf). Layers com cor (true color) e espessura; ponto → POINT
# (+ TEXT de rótulo ao lado); linha/polígono → LWPOLYLINE (2D) ou POLYLINE 3D (Z variável);
# texto solto → TEXT. Coordenadas em UTM (m) ou geodésicas (graus decimais: X = lon, Y = lat).
# ==============================================================================
from __future__ import annotations

import io
import re

import ezdxf
import numpy as np
from ezdxf import colors
from ezdxf.lldxf.const import VALID_DXF_LINEWEIGHTS

from core.crs import SistemaRef, de_geografico
from core.modelo import Estilo, Projeto, TipoFeicao

ALTURA_TEXTO_M = 0.5
M_POR_GRAU = 111_320.0


_PRETO_BRANCO = {(0, 0, 0), (255, 255, 255)}


def _cor_dxf(cor) -> dict:
    """Preto/branco saem como ACI 7 (preto no fundo branco, branco no fundo preto do CAD);
    as demais como true color."""
    if tuple(cor) in _PRETO_BRANCO:
        return {"color": 7}
    return {"true_color": colors.rgb2int(cor)}


def _lineweight(mm: float) -> int:
    alvo = round(mm * 100)
    return min(VALID_DXF_LINEWEIGHTS, key=lambda w: abs(w - alvo))


def nome_layer(nome: str) -> str:
    return re.sub(r'[<>/\\":;?*|=`]', "_", nome).strip() or "0"


def escrever_dxf(proj: Projeto, sistema: SistemaRef) -> bytes:
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 6 if sistema.tipo == "UTM" else 0     # 6 = metros
    msp = doc.modelspace()
    altura = ALTURA_TEXTO_M if sistema.tipo == "UTM" else ALTURA_TEXTO_M / M_POR_GRAU

    def aplicar(dxf: dict, est: Estilo):
        dxf["lineweight"] = _lineweight(est.espessura)
        if est.tipo_linha in doc.linetypes:
            dxf["linetype"] = est.tipo_linha

    for nome, cam in proj.camadas.items():
        n = nome_layer(nome)
        layer = doc.layers.get(n) if n in doc.layers else doc.layers.add(n)
        attrs = _cor_dxf(cam.estilo.cor)
        aplicar(attrs, cam.estilo)
        for k, v in attrs.items():
            layer.dxf.set(k, v)
        if not cam.visivel:
            layer.off()

    for f in proj.feicoes:
        cam = proj.camadas[f.layer]
        dxf = {"layer": nome_layer(f.layer)}
        if f.estilo is not None and f.estilo != cam.estilo:     # sobrescreve o ByLayer
            dxf.update(_cor_dxf(f.estilo.cor))
            aplicar(dxf, f.estilo)
        x, y = de_geografico(sistema, f.coords[:, 0], f.coords[:, 1])
        z = f.coords[:, 2] if f.tem_z else np.zeros(len(x))

        if f.tipo == TipoFeicao.PONTO:
            msp.add_point((x[0], y[0], z[0]), dxfattribs=dxf)
            if f.texto:
                msp.add_text(f.texto, height=altura, dxfattribs=dxf) \
                    .set_placement((x[0] + altura * 0.5, y[0] + altura * 0.5, z[0]))
        elif f.tipo == TipoFeicao.TEXTO:
            msp.add_text(f.texto or "", height=altura, dxfattribs=dxf) \
                .set_placement((x[0], y[0], z[0]))
        else:
            fechado = f.tipo == TipoFeicao.POLIGONO
            if f.tem_z and np.ptp(z) > 0:
                pts = list(zip(x, y, z))
                msp.add_polyline3d(pts, close=fechado, dxfattribs=dxf)
            else:
                msp.add_lwpolyline(list(zip(x, y)), close=fechado,
                                   dxfattribs={**dxf, "elevation": float(z[0])})

    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")
