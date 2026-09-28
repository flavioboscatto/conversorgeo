# ==============================================================================
# Leitor KML/KMZ (lxml). Pastas → layers; estilos → cores; Placemark só com rótulo → texto.
# KML é WGS 84 geodésico; tratado como SIRGAS 2000 (diferença de poucos cm).
# ==============================================================================
from __future__ import annotations

import io
import zipfile

from lxml import etree

from core.crs import SistemaRef
from core.leitores import ErroLeitura
from core.leitores._comum import Bruta, montar_projeto, remover_fechamento
from core.modelo import Camada, Estilo, Projeto, TipoFeicao

PX_POR_MM = 4.0      # largura KML (px) ↔ espessura CAD (mm) — mesma regra do escritor


def _local(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _filho(el, nome):
    for f in el:
        if _local(f) == nome:
            return f
    return None


def _texto(el, nome) -> str:
    f = _filho(el, nome)
    return (f.text or "").strip() if f is not None else ""


def cor_kml_para_rgb(aabbggrr: str) -> tuple[int, int, int] | None:
    t = (aabbggrr or "").strip().lstrip("#")
    if len(t) != 8:
        return None
    try:
        return int(t[6:8], 16), int(t[4:6], 16), int(t[2:4], 16)
    except ValueError:
        return None


def _abrir(dados: bytes) -> bytes:
    if dados[:2] != b"PK":
        return dados
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            kmls = [n for n in z.namelist() if n.lower().endswith(".kml")]
            if not kmls:
                raise ErroLeitura("O KMZ não contém nenhum arquivo .kml.")
            kmls.sort(key=lambda n: (n.count("/"), n.lower() != "doc.kml"))
            return z.read(kmls[0])
    except zipfile.BadZipFile:
        raise ErroLeitura("O KMZ está corrompido (não é um ZIP válido).") from None


def _ler_estilo(st) -> dict:
    d = {}
    for sub in st:
        nome = _local(sub)
        if nome in ("LineStyle", "PolyStyle", "IconStyle", "LabelStyle"):
            d[nome] = {"cor": cor_kml_para_rgb(_texto(sub, "color"))}
            if nome == "LineStyle" and _texto(sub, "width"):
                try:
                    d[nome]["largura"] = float(_texto(sub, "width"))
                except ValueError:
                    pass
            if nome == "IconStyle" and _texto(sub, "scale"):
                try:
                    d[nome]["escala"] = float(_texto(sub, "scale"))
                except ValueError:
                    pass
    return d


def _estilos(raiz) -> dict[str, dict]:
    estilos, mapas = {}, {}
    for el in raiz.iter():
        nome = _local(el)
        ident = el.get("id")
        if not ident:
            continue
        if nome == "Style":
            estilos[ident] = _ler_estilo(el)
        elif nome == "StyleMap":
            for par in el:
                if _local(par) == "Pair" and _texto(par, "key") == "normal":
                    mapas[ident] = _texto(par, "styleUrl").split("#")[-1]
    for ident, alvo in mapas.items():
        estilos[ident] = estilos.get(alvo, {})
    return estilos


def _coords(texto: str) -> list:
    pts = []
    for tupla in (texto or "").split():
        partes = tupla.split(",")
        if len(partes) >= 2:
            try:
                pts.append((float(partes[0]), float(partes[1]),
                            float(partes[2]) if len(partes) > 2 and partes[2] else 0.0))
            except ValueError:
                continue
    return pts


def _geometrias(el):
    """(tipo, pontos) para Point, LineString, LinearRing, Polygon e MultiGeometry."""
    for g in el:
        nome = _local(g)
        if nome == "Point":
            yield "Point", _coords(_texto(g, "coordinates"))
        elif nome == "LineString":
            yield "LineString", _coords(_texto(g, "coordinates"))
        elif nome == "LinearRing":
            yield "Polygon", _coords(_texto(g, "coordinates"))
        elif nome == "Polygon":
            externo = _filho(g, "outerBoundaryIs")
            anel = _filho(externo, "LinearRing") if externo is not None else None
            if anel is not None:
                yield "Polygon", _coords(_texto(anel, "coordinates"))
        elif nome == "MultiGeometry":
            yield from _geometrias(g)


def _atributos(pm) -> dict:
    attrs = {}
    ext = _filho(pm, "ExtendedData")
    if ext is not None:
        for el in ext.iter():
            nome = _local(el)
            if nome == "Data" and el.get("name"):
                attrs[el.get("name")] = _texto(el, "value")
            elif nome == "SimpleData" and el.get("name"):
                attrs[el.get("name")] = (el.text or "").strip()
    return attrs


def _estilo_de(pm, estilos, tipo: str) -> tuple[Estilo | None, float]:
    """(Estilo, escala do ícone) a partir de styleUrl ou Style embutido."""
    d = {}
    url = _texto(pm, "styleUrl")
    if url:
        d = estilos.get(url.split("#")[-1], {})
    inline = _filho(pm, "Style")
    if inline is not None:
        d = {**d, **_ler_estilo(inline)}
    escala = d.get("IconStyle", {}).get("escala", 1.0)
    if tipo == "Point":
        cor = d.get("IconStyle", {}).get("cor") or d.get("LabelStyle", {}).get("cor")
        return (Estilo(cor) if cor else None), escala
    ls = d.get("LineStyle", {})
    cor = ls.get("cor") or d.get("PolyStyle", {}).get("cor")
    if cor is None and "largura" not in ls:
        return None, escala
    return Estilo(cor or (255, 255, 255), ls.get("largura", 1.0) / PX_POR_MM), escala


def ler_kml(dados: bytes) -> Projeto:
    xml = _abrir(dados)
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, recover=True)
    try:
        raiz = etree.fromstring(xml, parser)
    except etree.XMLSyntaxError:
        raiz = None
    if raiz is None:
        raise ErroLeitura("O arquivo não é um KML válido.")
    estilos = _estilos(raiz)
    brutas: list[Bruta] = []
    camadas: dict[str, Camada] = {}

    def percorrer(el, pasta: str):
        for f in el:
            nome = _local(f)
            if nome == "Folder":
                percorrer(f, _texto(f, "name") or pasta)
            elif nome == "Document":
                percorrer(f, pasta if pasta != "KML" else (_texto(f, "name") or "KML"))
            elif nome == "Placemark":
                rotulo = _texto(f, "name")
                attrs = _atributos(f)
                for tipo, pts in _geometrias(f):
                    if not pts:
                        continue
                    est, escala = _estilo_de(f, estilos, tipo)
                    if est and pasta not in camadas:
                        camadas[pasta] = Camada(pasta, est)
                    if tipo == "Point":
                        if escala == 0 and rotulo:
                            brutas.append(Bruta(TipoFeicao.TEXTO, pts[:1], pasta, est, rotulo, attrs))
                        else:
                            brutas.append(Bruta(TipoFeicao.PONTO, pts[:1], pasta, est, rotulo, attrs))
                    elif tipo == "LineString":
                        brutas.append(Bruta(TipoFeicao.LINHA, pts, pasta, est, None, attrs))
                    else:
                        anel = remover_fechamento(pts)
                        t = TipoFeicao.POLIGONO if len(anel) >= 3 else TipoFeicao.LINHA
                        brutas.append(Bruta(t, anel, pasta, est, None, attrs))
            elif nome == "kml":
                percorrer(f, pasta)

    percorrer([raiz], "KML")     # a raiz pode ser <kml>, <Document> ou <Folder>
    return montar_projeto(SistemaRef.geografico(), brutas, camadas, "KML")
