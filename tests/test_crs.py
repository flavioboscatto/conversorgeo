"""Testes da Etapa 1 — SistemaRef, conversões, aviso de fuso e modelo interno."""
import numpy as np
import pytest
from pyproj import CRS

from core.crs import (FUSOS_NORTE, FUSOS_SUL, SistemaRef, aviso_fuso,
                      aviso_hemisferio, converter,
                      de_geografico, para_geografico, pontos_fora_do_fuso,
                      sugerir_fuso, sugerir_hemisferio)
from core.modelo import Camada, Estilo, Feicao, Projeto, TipoFeicao

TOL_M = 0.001


# ------------------------------------------------------------- SistemaRef
@pytest.mark.parametrize("fuso", FUSOS_SUL)
def test_epsg_sul(fuso):
    s = SistemaRef.utm(fuso, "S")
    assert CRS.from_epsg(s.epsg).name == f"SIRGAS 2000 / UTM zone {fuso}S"


@pytest.mark.parametrize("fuso", FUSOS_NORTE)
def test_epsg_norte(fuso):
    s = SistemaRef.utm(fuso, "N")
    assert CRS.from_epsg(s.epsg).name == f"SIRGAS 2000 / UTM zone {fuso}N"


def test_epsg_geografico():
    assert SistemaRef.geografico().epsg == 4674


@pytest.mark.parametrize("fuso,hem", [(16, "S"), (26, "S"), (25, "N"), (22, "X"), (None, "S")])
def test_sistema_invalido(fuso, hem):
    with pytest.raises(ValueError):
        SistemaRef("UTM", fuso, hem)


def test_meridiano_central():
    assert SistemaRef.utm(22, "S").meridiano_central == -51.0
    assert SistemaRef.utm(23, "S").meridiano_central == -45.0


# ------------------------------------------------------------- sugestões
@pytest.mark.parametrize("lon,fuso", [(-48.5, 22), (-51.0, 22), (-54.0, 22), (-53.99, 22),
                                      (-46.6, 23), (-60.0, 21), (-35.0, 25), (-72.0, 19)])
def test_sugerir_fuso(lon, fuso):
    assert sugerir_fuso(lon) == fuso


def test_sugerir_hemisferio():
    assert sugerir_hemisferio(-27.0) == "S"
    assert sugerir_hemisferio(2.5) == "N"


# ------------------------------------------------------------- conversões
def test_ida_e_volta_utm_geo_utm_vetorial():
    s = SistemaRef.utm(22, "S")
    rng = np.random.default_rng(42)
    e = rng.uniform(200_000, 800_000, 200)
    n = rng.uniform(6_600_000, 7_300_000, 200)
    lon, lat = para_geografico(s, e, n)
    e2, n2 = de_geografico(s, lon, lat)
    assert e2.dtype == np.float64 and n2.dtype == np.float64
    assert np.max(np.abs(e2 - e)) < TOL_M
    assert np.max(np.abs(n2 - n)) < TOL_M


def test_ida_e_volta_hemisferio_norte():
    s = SistemaRef.utm(22, "N")
    lon, lat = np.array([-51.2, -50.1]), np.array([1.5, 3.9])
    e, n = de_geografico(s, lon, lat)
    lon2, lat2 = para_geografico(s, e, n)
    e2, n2 = de_geografico(s, lon2, lat2)
    assert np.max(np.abs(e2 - e)) < TOL_M and np.max(np.abs(n2 - n)) < TOL_M


def test_geo_para_geo_identidade():
    g = SistemaRef.geografico()
    x, y = converter(g, g, [-48.5], [-27.6])
    assert x[0] == -48.5 and y[0] == -27.6


def test_escalar_vira_array():
    lon, lat = para_geografico(SistemaRef.utm(22, "S"), 745_000.0, 6_945_000.0)
    assert lon.shape == (1,) and lat.shape == (1,)


def test_troca_de_fuso():
    """Ponto convertido de 22S para 23S e de volta volta ao mesmo lugar."""
    s22, s23 = SistemaRef.utm(22, "S"), SistemaRef.utm(23, "S")
    e, n = np.array([745_000.0]), np.array([6_945_000.0])
    e23, n23 = converter(s22, s23, e, n)
    e22, n22 = converter(s23, s22, e23, n23)
    assert abs(e22[0] - e[0]) < TOL_M and abs(n22[0] - n[0]) < TOL_M


# ------------------------------------------------------------- aviso de fuso
def test_aviso_fuso_dispara():
    s = SistemaRef.utm(22, "S")                    # MC -51°
    lon = np.array([-48.5, -50.0, -46.6])          # -46,6 está a 4,4° do MC
    assert list(pontos_fora_do_fuso(s, lon)) == [2]
    msg = aviso_fuso(s, lon)
    assert msg is not None and "1 ponto" in msg and "22S" in msg


def test_aviso_fuso_nao_dispara():
    s = SistemaRef.utm(22, "S")
    assert aviso_fuso(s, [-48.5, -51.0, -53.9, -48.0]) is None   # exatamente 3° não avisa


def test_aviso_hemisferio():
    assert "Sul" in aviso_hemisferio(SistemaRef.utm(22, "N"), [-27.6])
    assert "Norte" in aviso_hemisferio(SistemaRef.utm(22, "S"), [-27.6, 1.5])
    assert aviso_hemisferio(SistemaRef.utm(22, "S"), [-27.6, 0.0]) is None
    assert aviso_hemisferio(SistemaRef.geografico(), [10.0]) is None


def test_aviso_fuso_geografico_nunca_dispara():
    assert aviso_fuso(SistemaRef.geografico(), [-10.0, -80.0]) is None


# ------------------------------------------------------------- modelo
def test_feicao_float64_e_forma():
    f = Feicao(TipoFeicao.PONTO, [-48.5, -27.6])
    assert f.coords.dtype == np.float64 and f.coords.shape == (1, 2) and not f.tem_z
    f3 = Feicao("linha", np.array([[0, 0, 1], [1, 1, 2]], dtype=np.float32))
    assert f3.coords.dtype == np.float64 and f3.tem_z


@pytest.mark.parametrize("tipo,coords", [
    ("linha", [[0, 0]]),
    ("poligono", [[0, 0], [1, 1]]),
    ("ponto", [[0, 0, 0, 0]]),
    ("ponto", np.empty((0, 2))),
])
def test_feicao_invalida(tipo, coords):
    with pytest.raises(ValueError):
        Feicao(tipo, coords)


def test_estilo_invalido():
    with pytest.raises(ValueError):
        Estilo(cor=(300, 0, 0))


def test_projeto_cria_camadas_e_resumo():
    p = Projeto(SistemaRef.utm(22, "S"))
    p.adicionar(Feicao("ponto", [0, 0], layer="VERTICES"))
    p.adicionar(Feicao("linha", [[0, 0], [1, 1]], layer="DIVISA"))
    p.adicionar(Feicao("ponto", [1, 1], layer="VERTICES", estilo=Estilo((255, 0, 0))))
    assert set(p.camadas) == {"VERTICES", "DIVISA"}
    assert p.resumo()["ponto"] == 2 and p.resumo()["linha"] == 1
    assert p.estilo_de(p.feicoes[2]).cor == (255, 0, 0)
    assert p.estilo_de(p.feicoes[0]) is p.camadas["VERTICES"].estilo
    assert isinstance(p.camadas["DIVISA"], Camada)


def test_juntar_projetos_com_layer_repetida():
    from core.modelo import juntar
    a = Projeto(SistemaRef.utm(22, "S"))
    a.adicionar(Feicao("ponto", [-48.5, -27.6], layer="DIVISA"))
    a.avisos.append("aviso A")
    b = Projeto(SistemaRef.geografico())
    b.adicionar(Feicao("linha", [[-48.5, -27.6], [-48.4, -27.5]], layer="DIVISA"))
    b.adicionar(Feicao("ponto", [-48.4, -27.5], layer="MARCOS"))
    t = juntar([("lote1", a), ("lote2", b)])
    assert set(t.camadas) == {"DIVISA", "lote2_DIVISA", "MARCOS"}
    assert [f.layer for f in t.feicoes] == ["DIVISA", "lote2_DIVISA", "MARCOS"]
    assert t.camadas["lote2_DIVISA"].nome == "lote2_DIVISA"
    assert t.feicoes[1].coords is b.feicoes[0].coords          # sem cópia
    assert b.feicoes[0].layer == "DIVISA"                      # originais intactos
    assert t.avisos == ["lote1: aviso A"]
    assert t.resumo()["ponto"] == 2 and t.resumo()["linha"] == 1
