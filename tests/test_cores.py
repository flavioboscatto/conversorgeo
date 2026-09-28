"""Cor 7 do AutoCAD, troca de cor por layer e mensagem de sistema desconhecido."""
import io

import ezdxf
import pytest

from core.conversor import escrever, ler
from core.crs import SistemaRef
from core.leitores import ErroLeitura
from core.modelo import juntar, recolorir
from tests.exemplo_dxf import exemplo_bytes
from ui.mapa import hex_para_rgb

UTM22S = SistemaRef.utm(22, "S")
GEO = SistemaRef.geografico()


@pytest.fixture(scope="module")
def proj():
    return ler("DXF", exemplo_bytes(), UTM22S)


def test_aci7_branco_do_autocad_vira_preto(proj):
    assert proj.camadas["TEXTOS"].estilo.cor == (0, 0, 0)


def test_preto_sai_como_aci7_no_dxf(proj):
    dados, _ = escrever(proj, "DXF", UTM22S, "x")
    doc = ezdxf.read(io.StringIO(dados.decode("utf-8")))
    ly = doc.layers.get("TEXTOS")
    assert ly.dxf.color == 7 and not ly.dxf.hasattr("true_color")
    assert doc.layers.get("ARRUAMENTO").rgb == (255, 128, 0)


def test_recolorir_vale_para_saida_sem_mexer_no_original(proj):
    total = juntar([("a", proj)])
    recolorir(total, "EDIFICACAO", (10, 20, 30))
    assert total.camadas["EDIFICACAO"].estilo.cor == (10, 20, 30)
    assert all(total.estilo_de(f).cor == (10, 20, 30)
               for f in total.feicoes if f.layer == "EDIFICACAO")
    assert proj.camadas["EDIFICACAO"].estilo.cor == (0, 255, 255)        # original intacto
    kml, _ = escrever(total, "KML", GEO, "x", kmz=False)
    assert b"ff1e140a" in kml                                           # aabbggrr


def test_sistema_desconhecido_explica_reprojecao():
    doc = ezdxf.new("R2018")
    doc.modelspace().add_lwpolyline([(-5401872.1, -3198591.9), (-5401858.9, -3198600.2)])
    buf = io.StringIO()
    doc.write(buf)
    with pytest.raises(ErroLeitura, match="reprojete"):
        ler("DXF", buf.getvalue().encode(), UTM22S)


def test_hex_para_rgb():
    assert hex_para_rgb("#ff8000") == (255, 128, 0)
    assert hex_para_rgb("rgb(1,2,3)") is None
