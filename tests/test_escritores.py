"""Etapas 3 e 4 — escritores KML/KMZ, Shapefile e DXF; leitores KML e SHP; ida e volta."""
import io
import zipfile

import numpy as np
import pytest
import shapefile
from lxml import etree
from pyproj import CRS

from core.conversor import escrever, ler
from core.crs import SistemaRef, de_geografico, sistema_de_prj, wkt_prj
from core.escritores.kml import png_circulo, rgb_para_kml
from core.escritores.shp import nome_campo
from core.leitores import ErroLeitura
from core.leitores.kml import cor_kml_para_rgb
from core.modelo import TipoFeicao
from tests.exemplo_dxf import exemplo_bytes

UTM22S = SistemaRef.utm(22, "S")
GEO = SistemaRef.geografico()
TOL_M = 0.001


@pytest.fixture(scope="module")
def proj():
    return ler("DXF", exemplo_bytes(), UTM22S)


def _assinatura(p):
    """Contagem por (layer, tipo) — deve sobreviver às conversões."""
    c = {}
    for f in p.feicoes:
        c[(f.layer, f.tipo)] = c.get((f.layer, f.tipo), 0) + 1
    return c


def _ordenadas(p):
    ordem = {TipoFeicao.PONTO: 0, TipoFeicao.TEXTO: 1, TipoFeicao.LINHA: 2, TipoFeicao.POLIGONO: 3}
    return sorted(p.feicoes, key=lambda f: (f.layer, ordem[f.tipo], len(f.coords),
                                            round(f.coords[0, 0], 7), round(f.coords[0, 1], 7)))


def _max_residuo_m(a, b):
    """Maior distância (m, em UTM 22S) entre vértices correspondentes de dois projetos."""
    pior = 0.0
    fas, fbs = _ordenadas(a), _ordenadas(b)
    assert len(fas) == len(fbs)
    for fa, fb in zip(fas, fbs):
        assert fa.coords.shape[0] == fb.coords.shape[0]
        ea, na = de_geografico(UTM22S, fa.coords[:, 0], fa.coords[:, 1])
        eb, nb = de_geografico(UTM22S, fb.coords[:, 0], fb.coords[:, 1])
        d = float(np.max(np.hypot(ea - eb, na - nb)))
        if fa.tipo == TipoFeicao.POLIGONO:      # SHP grava anel horário: aceita sentido inverso
            inv = np.r_[0, np.arange(len(eb) - 1, 0, -1)]
            d = min(d, float(np.max(np.hypot(ea - eb[inv], na - nb[inv]))))
        pior = max(pior, d)
    return pior


# ------------------------------------------------------------------ KML
def test_cor_kml_ida_e_volta():
    assert rgb_para_kml((255, 128, 0)) == "ff0080ff"
    assert cor_kml_para_rgb("ff0080ff") == (255, 128, 0)


def test_kmz_estrutura(proj):
    dados, nome = escrever(proj, "KML", GEO, "exemplo.dxf", kmz=True)
    assert nome == "exemplo.kmz"
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        assert set(z.namelist()) == {"doc.kml", "files/circulo.png"}
        assert z.read("files/circulo.png") == png_circulo()
        raiz = etree.fromstring(z.read("doc.kml"))
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    pastas = [p.findtext("k:name", namespaces=ns) for p in raiz.iterfind(".//k:Folder", ns)]
    assert set(pastas) == set(proj.camadas)
    assert raiz.find(".//k:Icon/k:href", ns).text == "files/circulo.png"
    assert raiz.find(".//k:IconStyle[k:scale='0']", ns) is not None     # texto solto sem ícone


def test_kml_nunca_utm(proj):
    with pytest.raises(ValueError):
        escrever(proj, "KML", UTM22S, "x")


@pytest.mark.parametrize("kmz", [True, False])
def test_dxf_kml_dxf_ida_e_volta(proj, kmz):
    kml, _ = escrever(proj, "KML", GEO, "x", kmz=kmz)
    p2 = ler("KML", kml, GEO)
    assert _assinatura(p2) == _assinatura(proj)
    assert _max_residuo_m(proj, p2) < TOL_M
    dxf, _ = escrever(p2, "DXF", UTM22S, "x")
    p3 = ler("DXF", dxf, UTM22S)
    assert _assinatura(p3) == _assinatura(proj)
    assert _max_residuo_m(proj, p3) < TOL_M
    assert p3.camadas["DIVISA"].estilo.cor == proj.camadas["DIVISA"].estilo.cor
    assert sorted(f.texto for f in p3.feicoes if f.texto) == \
        sorted(f.texto for f in proj.feicoes if f.texto)


def test_kml_invalido():
    with pytest.raises(ErroLeitura):
        ler("KML", b"<isto nao e kml", GEO)


# ------------------------------------------------------------------ SHP
def test_prj_confere_com_pyproj():
    for s, epsg in [(UTM22S, 31982), (SistemaRef.utm(23, "S"), 31983),
                    (SistemaRef.utm(22, "N"), 31976), (GEO, 4674)]:
        crs = CRS.from_wkt(wkt_prj(s))
        assert crs.to_epsg(min_confidence=70) == epsg, s


@pytest.mark.parametrize("epsg,esperado", [(31982, UTM22S), (31983, SistemaRef.utm(23, "S")),
                                            (31976, SistemaRef.utm(22, "N")), (4674, GEO)])
def test_prj_lido_de_wkt_do_pyproj(epsg, esperado):
    for versao in ("WKT1_ESRI", "WKT1_GDAL"):
        s, aviso = sistema_de_prj(CRS.from_epsg(epsg).to_wkt(versao))
        assert s == esperado and aviso is None


def test_prj_datum_diferente_avisa():
    _, aviso = sistema_de_prj(CRS.from_epsg(29192).to_wkt("WKT1_ESRI"))    # SAD69 / UTM 22S
    assert aviso and "datum" in aviso


def test_nome_campo_dbf():
    usados = set()
    assert nome_campo("confrontante", usados) == "CONFRONTAN"
    assert nome_campo("confrontante_2", usados) == "CONFRONTA1"
    assert nome_campo("Método", usados) == "METODO"


def test_shp_estrutura(proj):
    dados, nome = escrever(proj, "SHP", UTM22S, "exemplo.dxf")
    assert nome == "exemplo_shp.zip"
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nomes = set(z.namelist())
        for sufixo in ("pontos", "linhas", "poligonos"):
            for ext in ("shp", "shx", "dbf", "prj", "cpg"):
                assert f"exemplo_{sufixo}.{ext}" in nomes
        r = shapefile.Reader(shp=io.BytesIO(z.read("exemplo_pontos.shp")),
                             dbf=io.BytesIO(z.read("exemplo_pontos.dbf")))
        assert r.shapeType == shapefile.POINTZ
        campos = [f[0] for f in r.fields[1:]]
        assert campos[:5] == ["LAYER", "TIPO", "COR", "ESPESSURA", "TEXTO"]
        assert "BLOCO" in campos and "NUM" in campos
        assert z.read("exemplo_pontos.cpg") == b"UTF-8"


@pytest.mark.parametrize("sistema", [UTM22S, GEO])
def test_dxf_shp_ida_e_volta(proj, sistema):
    dados, _ = escrever(proj, "SHP", sistema, "x")
    p2 = ler("SHP", dados, SistemaRef.utm(23, "S"))        # sistema informado é ignorado: tem .prj
    assert p2.crs_origem == sistema
    assert _assinatura(p2) == _assinatura(proj)
    assert _max_residuo_m(proj, p2) < TOL_M
    assert p2.camadas["DIVISA"].estilo.cor == proj.camadas["DIVISA"].estilo.cor


def test_shp_sem_prj_usa_sistema_informado(proj):
    dados, _ = escrever(proj, "SHP", UTM22S, "x")
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(dados)) as zin, zipfile.ZipFile(buf, "w") as zout:
        for n in zin.namelist():
            if not n.endswith(".prj"):
                zout.writestr(n, zin.read(n))
    p2 = ler("SHP", buf.getvalue(), UTM22S)
    assert p2.crs_origem == UTM22S
    assert any("não tem .prj" in a for a in p2.avisos)


def test_shp_zip_invalido():
    with pytest.raises(ErroLeitura, match="ZIP"):
        ler("SHP", b"nao e zip", UTM22S)


# ------------------------------------------------------------------ DXF
def test_dxf_geodesico_saida(proj):
    dados, _ = escrever(proj, "DXF", GEO, "x")
    p2 = ler("DXF", dados, GEO)
    assert _assinatura(p2) == _assinatura(proj)
    assert _max_residuo_m(proj, p2) < TOL_M
