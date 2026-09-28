# ==============================================================================
# Escritor KML/KMZ. Uma pasta por layer; cor RGB → aabbggrr; espessura mantida.
# Ponto: ícone de círculo (embutido no KMZ, colorido pelo IconStyle), rótulo = texto.
# Texto solto: placemark só com rótulo (IconStyle scale 0).
# Limitação: tracejados não existem no KML.
# ==============================================================================
from __future__ import annotations

import html
import io
import math
import struct
import zipfile
import zlib
from functools import lru_cache

from lxml import etree

from core.modelo import Estilo, Projeto, TipoFeicao

NS = "http://www.opengis.net/kml/2.2"
PX_POR_MM = 4.0
ICONE_KMZ = "files/circulo.png"
ICONE_KML = "https://maps.google.com/mapfiles/kml/shapes/shaded_dot.png"


@lru_cache(maxsize=1)
def png_circulo(tam: int = 32) -> bytes:
    """Círculo branco com borda preta (o branco recebe a cor do IconStyle)."""
    c = (tam - 1) / 2
    linhas = []
    for y in range(tam):
        px = bytearray(b"\x00")
        for x in range(tam):
            d = math.hypot(x - c, y - c)
            px += b"\xff\xff\xff\xff" if d <= tam * 0.36 else (
                b"\x00\x00\x00\xff" if d <= tam * 0.46 else b"\x00\x00\x00\x00")
        linhas.append(bytes(px))

    def bloco(tipo, dados):
        return (struct.pack(">I", len(dados)) + tipo + dados
                + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n"
            + bloco(b"IHDR", struct.pack(">IIBBBBB", tam, tam, 8, 6, 0, 0, 0))
            + bloco(b"IDAT", zlib.compress(b"".join(linhas)))
            + bloco(b"IEND", b""))


def rgb_para_kml(cor, alfa: int = 255) -> str:
    r, g, b = cor
    return f"{alfa:02x}{b:02x}{g:02x}{r:02x}"


def _sub(pai, nome, texto=None, **attrs):
    el = etree.SubElement(pai, f"{{{NS}}}{nome}", **attrs)
    if texto is not None:
        el.text = str(texto)
    return el


def _coord(c) -> str:
    if len(c) == 3:
        return f"{c[0]:.10f},{c[1]:.10f},{c[2]:.3f}"
    return f"{c[0]:.10f},{c[1]:.10f}"


def _descricao(f) -> str | None:
    if not f.atributos:
        return None
    linhas = "".join(f"<tr><td><b>{html.escape(str(k))}</b></td><td>{html.escape(str(v))}</td></tr>"
                     for k, v in f.atributos.items())
    return f"<table>{linhas}</table>"


def escrever_kml(proj: Projeto, kmz: bool = True, nome_doc: str = "Conversor Geo") -> bytes:
    raiz = etree.Element(f"{{{NS}}}kml", nsmap={None: NS})
    doc = _sub(raiz, "Document")
    _sub(doc, "name", nome_doc)
    icone = ICONE_KMZ if kmz else ICONE_KML
    estilos: dict[tuple, str] = {}

    def estilo_id(tipo: TipoFeicao, est: Estilo) -> str:
        chave = (tipo, est.cor, round(est.espessura, 2))
        if chave in estilos:
            return estilos[chave]
        ident = f"e{len(estilos) + 1}"
        estilos[chave] = ident
        st = _sub(doc, "Style", id=ident)
        cor = rgb_para_kml(est.cor)
        if tipo in (TipoFeicao.PONTO, TipoFeicao.TEXTO):
            ic = _sub(st, "IconStyle")
            _sub(ic, "color", cor)
            if tipo == TipoFeicao.TEXTO:
                _sub(ic, "scale", "0")
            else:
                _sub(ic, "scale", "0.6")
                _sub(_sub(ic, "Icon"), "href", icone)
            lb = _sub(st, "LabelStyle")
            _sub(lb, "color", cor if tipo == TipoFeicao.TEXTO else "ffffffff")
            _sub(lb, "scale", "0.8")
        else:
            ls = _sub(st, "LineStyle")
            _sub(ls, "color", cor)
            _sub(ls, "width", f"{max(1.0, est.espessura * PX_POR_MM):.1f}")
            if tipo == TipoFeicao.POLIGONO:
                ps = _sub(st, "PolyStyle")
                _sub(ps, "color", rgb_para_kml(est.cor, 64))
                _sub(ps, "fill", "0")
        return ident

    pastas = {}
    for nome, cam in proj.camadas.items():
        pasta = _sub(doc, "Folder")
        _sub(pasta, "name", nome)
        if not cam.visivel:
            _sub(pasta, "visibility", "0")
        pastas[nome] = pasta

    for f in proj.feicoes:
        pm = _sub(pastas[f.layer], "Placemark")
        if f.texto:
            _sub(pm, "name", f.texto)
        desc = _descricao(f)
        if desc:
            _sub(pm, "description").text = etree.CDATA(desc)
        _sub(pm, "styleUrl", "#" + estilo_id(f.tipo, proj.estilo_de(f)))
        if f.atributos:
            ext = _sub(pm, "ExtendedData")
            for k, v in f.atributos.items():
                _sub(_sub(ext, "Data", name=str(k)), "value", v)
        if f.tipo in (TipoFeicao.PONTO, TipoFeicao.TEXTO):
            _sub(_sub(pm, "Point"), "coordinates", _coord(f.coords[0]))
        elif f.tipo == TipoFeicao.LINHA:
            ls = _sub(pm, "LineString")
            _sub(ls, "tessellate", "1")
            _sub(ls, "coordinates", " ".join(_coord(c) for c in f.coords))
        else:
            anel = list(f.coords) + [f.coords[0]]
            pg = _sub(pm, "Polygon")
            _sub(pg, "tessellate", "1")
            lr = _sub(_sub(pg, "outerBoundaryIs"), "LinearRing")
            _sub(lr, "coordinates", " ".join(_coord(c) for c in anel))

    xml = etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", pretty_print=True)
    if not kmz:
        return xml
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", xml)
        z.writestr(ICONE_KMZ, png_circulo())
    return buf.getvalue()
