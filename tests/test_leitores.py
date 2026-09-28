"""Etapa 2 — leitores DXF e SIGEF."""
import math
from pathlib import Path

import numpy as np
import pytest

from core.crs import SistemaRef, de_geografico, para_geografico
from core.leitores import ErroLeitura
from core.leitores.dxf import ler_dxf
from core.leitores.sigef import ler_sigef
from core.modelo import TipoFeicao
from tests.exemplo_dxf import E0, N0, exemplo_bytes

UTM22S = SistemaRef.utm(22, "S")
TOL_M = 0.001    # aceite do plano: 1 mm
SIGEF_ODS = Path(__file__).parent / "dados" / "SIGEF.ods"


@pytest.fixture(scope="module")
def proj_dxf():
    return ler_dxf(exemplo_bytes(), UTM22S)


def _utm(f):
    e, n = de_geografico(UTM22S, f.coords[:, 0], f.coords[:, 1])
    return np.column_stack([e, n])


def _de(proj, layer, tipo):
    return [f for f in proj.feicoes if f.layer == layer and f.tipo == tipo]


# ------------------------------------------------------------------ DXF
def test_dxf_contagens(proj_dxf):
    r = proj_dxf.resumo()
    # 4 vértices + 1 INSERT; linha, arco verde, arco espelhado; divisa, círculo, hatch; MTEXT
    assert r == {"ponto": 5, "linha": 3, "poligono": 3, "texto": 1}


def test_dxf_texto_vira_rotulo_do_ponto(proj_dxf):
    rotulos = sorted(f.texto for f in _de(proj_dxf, "VERTICES", TipoFeicao.PONTO) if f.texto)
    assert rotulos == ["P1", "P2", "P3", "P4"]
    soltos = [f.texto for f in proj_dxf.feicoes if f.tipo == TipoFeicao.TEXTO]
    assert soltos == ["Área de teste"]


def test_dxf_coordenadas_e_z(proj_dxf):
    p1 = next(f for f in proj_dxf.feicoes if f.texto == "P1")
    assert p1.coords.shape == (1, 3) and p1.coords[0, 2] == pytest.approx(11.0)
    e, n = _utm(p1)[0]
    assert abs(e - E0) < TOL_M and abs(n - N0) < TOL_M


def test_dxf_bulge_discretizado(proj_dxf):
    divisa = _de(proj_dxf, "DIVISA", TipoFeicao.POLIGONO)[0]
    xy = _utm(divisa)
    # semicírculo de P2 a P3: centro (E0+60, N0+20), raio 20, 180 passos de 1°
    arco = xy[1:180]
    raios = np.hypot(arco[:, 0] - (E0 + 60), arco[:, 1] - (N0 + 20))
    assert np.allclose(raios, 20.0, atol=TOL_M)
    assert len(xy) == 4 + 179
    assert xy[:, 0].max() == pytest.approx(E0 + 80, abs=1e-3)   # bulge > 0 vai para leste


def test_dxf_arco_espelhado_ocs(proj_dxf):
    arcos = _de(proj_dxf, "EDIFICACAO", TipoFeicao.LINHA)
    espelhado = next(a for a in arcos if len(a.coords) == 181 and
                     abs(np.hypot(*(_utm(a)[0] - (E0 + 30, N0 + 10))) - 3) < TOL_M)
    xy = _utm(espelhado)
    assert np.allclose(np.hypot(xy[:, 0] - (E0 + 30), xy[:, 1] - (N0 + 10)), 3.0, atol=TOL_M)


def test_dxf_cores_e_espessura(proj_dxf):
    assert proj_dxf.camadas["VERTICES"].estilo.cor == (255, 0, 0)
    assert proj_dxf.camadas["DIVISA"].estilo.espessura == pytest.approx(0.5)
    assert proj_dxf.camadas["ARRUAMENTO"].estilo.cor == (255, 128, 0)
    verde = [f for f in _de(proj_dxf, "EDIFICACAO", TipoFeicao.LINHA)
             if proj_dxf.estilo_de(f).cor == (0, 255, 0)]
    assert len(verde) == 1
    hatch = [f for f in _de(proj_dxf, "EDIFICACAO", TipoFeicao.POLIGONO) if len(f.coords) == 4]
    assert proj_dxf.estilo_de(hatch[0]).cor == (0, 0, 255)


def test_dxf_insert_com_atributos(proj_dxf):
    marco = next(f for f in proj_dxf.feicoes if f.atributos.get("BLOCO") == "MARCO")
    assert marco.atributos["NUM"] == "M-01"


def test_dxf_objeto_na_origem_ignorado_com_aviso(proj_dxf):
    assert any("fora da faixa" in a for a in proj_dxf.avisos)
    assert "0" not in proj_dxf.camadas


def test_dxf_sistema_errado():
    with pytest.raises(ErroLeitura, match="parecem UTM"):
        ler_dxf(exemplo_bytes(), SistemaRef.geografico())


def test_dxf_invalido():
    with pytest.raises(ErroLeitura):
        ler_dxf(b"isto nao e um dxf", UTM22S)


def test_dxf_em_geodesicas():
    """Mesmo desenho convertido para graus é lido como geodésico."""
    lon, lat = para_geografico(UTM22S, [E0], [N0])
    import ezdxf, io
    doc = ezdxf.new("R2018")
    doc.modelspace().add_point((lon[0], lat[0]))
    buf = io.StringIO()
    doc.write(buf)
    proj = ler_dxf(buf.getvalue().encode(), SistemaRef.geografico())
    assert proj.feicoes[0].coords[0, 0] == pytest.approx(lon[0], abs=1e-12)


# ------------------------------------------------------------------ SIGEF
@pytest.mark.skipif(not SIGEF_ODS.exists(), reason="planilha de teste fora do git")
def test_sigef_vertices_e_camadas():
    proj = ler_sigef(SIGEF_ODS.read_bytes())
    r = proj.resumo()
    assert r["ponto"] == 16 and r["linha"] == 16 and r["poligono"] == 1
    assert {"VERTICES_M", "VERTICES_P", "VERTICES_V", "LIMITES", "PERIMETRO"} <= set(proj.camadas)
    m1 = next(f for f in proj.feicoes if f.texto == "FBSC-M-0001")
    lat = -(27 + 35 / 60 + 39.554 / 3600)
    lon = -(48 + 32 / 60 + 28.781 / 3600)
    assert m1.coords[0, 0] == pytest.approx(lon, abs=1e-12)
    assert m1.coords[0, 1] == pytest.approx(lat, abs=1e-12)
    assert m1.coords[0, 2] == pytest.approx(13.23)
    assert m1.atributos["METODO"] == "PT5" and m1.atributos["LIMITE"] == "LA3"


@pytest.mark.skipif(not SIGEF_ODS.exists(), reason="planilha de teste fora do git")
def test_sigef_segmentos_com_confrontante():
    proj = ler_sigef(SIGEF_ODS.read_bytes())
    seg = next(f for f in proj.feicoes if f.tipo == TipoFeicao.LINHA
               and f.atributos["DE"] == "FBSC-V-0001")
    assert seg.atributos["PARA"] == "FBSC-V-0002"
    assert seg.atributos["MATRICULA"] == "2597"
    assert seg.atributos["CONFRONT"] == "Matrícula 2597"
    assert seg.atributos["CNS"] == ""
    ultimo = next(f for f in proj.feicoes if f.tipo == TipoFeicao.LINHA
                  and f.atributos["DE"] == "FBSC-P-0011")
    assert ultimo.atributos["PARA"] == "FBSC-M-0001"          # perímetro fecha no 1º


@pytest.mark.skipif(not SIGEF_ODS.exists(), reason="planilha de teste fora do git")
def test_sigef_nao_expoe_denominacao():
    proj = ler_sigef(SIGEF_ODS.read_bytes())
    textos = {str(v) for f in proj.feicoes for v in f.atributos.values()}
    assert "Beltrano de Tal" not in textos


def test_sigef_invalido():
    with pytest.raises(ErroLeitura):
        ler_sigef(b"nao e planilha")
