"""Leitor TXT/CSV: números, gg,mmss, separadores, colunas, layers por código e geometrias."""
import numpy as np
import pytest

from core.conversor import escrever, ler
from core.crs import SistemaRef
from core.geodesia.motor_geodesico import MotorGeodesico
from core.leitores import ErroLeitura
from core.leitores.txt import (ConfigTxt, detectar_cabecalho, detectar_separador,
                               ggmmss_para_decimal, numero, previa, sugerir_colunas)
from core.modelo import TipoFeicao

UTM22S = SistemaRef.utm(22, "S")
GEO = SistemaRef.geografico()
GMS = SistemaRef.geografico(gms=True)


def _pontos(proj):
    return [f for f in proj.feicoes if f.tipo == TipoFeicao.PONTO]


# ------------------------------------------------------------------ números e ângulos
@pytest.mark.parametrize("txt, esperado", [
    ("6945123,456", 6945123.456), ("6945123.456", 6945123.456),
    ("6.945.123,456", 6945123.456), ("-48,5", -48.5), ("  712 ", 712.0), ("+3.", 3.0),
])
def test_numero(txt, esperado):
    assert numero(txt) == pytest.approx(esperado, abs=1e-12)


@pytest.mark.parametrize("txt", ["", "abc", "1,2,3x", "12-3"])
def test_numero_invalido(txt):
    with pytest.raises(ValueError):
        numero(txt)


def test_ggmmss_igual_ao_formato_da_planilha_sigef():
    # mesmo ângulo escrito como na planilha do SIGEF (caminho de 3 blocos do motor)
    ref = MotorGeodesico.sexagesimal_para_decimal("27 35 43,092 S")
    assert ggmmss_para_decimal("-27,3543092") == pytest.approx(ref, abs=1e-12)
    assert ggmmss_para_decimal("-27.3543092") == pytest.approx(ref, abs=1e-12)


@pytest.mark.parametrize("txt, g, m, s", [
    ("-48,3228781", -48, 32, 28.781),
    ("48,5", 48, 50, 0.0),            # faltando dígitos: zeros à direita
    ("-0,3000", 0, 30, 0.0),          # sinal vale mesmo com 0 grau
    ("27", 27, 0, 0.0),
    ("-27,35430925", -27, 35, 43.0925),
])
def test_ggmmss(txt, g, m, s):
    sinal = -1 if txt.strip().startswith("-") else 1
    esperado = sinal * (abs(g) + m / 60 + s / 3600)
    assert ggmmss_para_decimal(txt) == pytest.approx(esperado, abs=1e-12)


@pytest.mark.parametrize("txt", ["-27,6043", "-27,3560", "abc", "-27,35,43"])
def test_ggmmss_invalido(txt):
    with pytest.raises(ValueError):
        ggmmss_para_decimal(txt)


# ------------------------------------------------------------------ separador, cabeçalho, colunas
@pytest.mark.parametrize("texto, sep", [
    ("P1;712000,123;6945000,456;10,5\nP2;712010;6945010;11\n", ";"),
    ("P1\t712000.1\t6945000.4\nP2\t712010\t6945010\n", "\t"),
    ("P1 712000.123  6945000.456 10.5\nP2   712010 6945010 11\n", " "),
    ("P1,712000.123,6945000.456\nP2,712010,6945010\n", ","),
    ("P1 712000,123 6945000,456\nP2 712010,5 6945010,5\n", " "),   # vírgula decimal, espaço separa
])
def test_detectar_separador(texto, sep):
    assert detectar_separador(texto) == sep


def test_cabecalho_e_sugestao_por_nome():
    linhas = previa(b"Ponto;N;E;Cota;Codigo\nP1;6945000;712000;10;CERCA\n", ";")
    assert detectar_cabecalho(linhas)
    sug = sugerir_colunas(linhas, True)
    assert sug == {"col_nome": 0, "col_x": 2, "col_y": 1, "col_z": 3, "col_codigo": 4}


def test_sugestao_sem_cabecalho():
    linhas = previa(b"P1;712000;6945000;10;CERCA\n", ";")
    assert not detectar_cabecalho(linhas)
    assert sugerir_colunas(linhas, False) == {
        "col_nome": 0, "col_x": 1, "col_y": 2, "col_z": 3, "col_codigo": 4}
    # nome numérico: 1, E, N, h
    linhas = previa(b"1;712000;6945000;10\n2;712001;6945001;10\n", ";")
    sug = sugerir_colunas(linhas, False)
    assert (sug["col_nome"], sug["col_x"], sug["col_y"], sug["col_z"]) == (0, 1, 2, 3)


def test_previa_ignora_vazias_e_comentarios_e_le_cp1252():
    dados = "# levantamento\n\nVÉRTICE;E;N\n".encode("cp1252")
    assert previa(dados, ";") == [["VÉRTICE", "E", "N"]]


# ------------------------------------------------------------------ leitura completa
def _arquivo_utm():
    """3 pontos UTM 22S gerados pelo motor a partir de lat/lon conhecidas."""
    geo = [(-27.5953, -48.5480), (-27.5960, -48.5470), (-27.5970, -48.5490)]
    linhas = ["Nome;E;N;h;Cod"]
    for i, (lat, lon) in enumerate(geo, 1):
        e, n = MotorGeodesico.lat_lon_para_utm(lat, lon, 22, "S")
        cod = "CERCA" if i < 3 else "POSTE"
        linhas.append(f"P{i};{e:.4f};{n:.4f};{10 + i},5;{cod}".replace(".", ","))
    return "\n".join(linhas).encode("utf-8"), geo


def test_utm_volta_para_as_geodesicas_de_origem():
    dados, geo = _arquivo_utm()
    cfg = ConfigTxt(";", True, col_x=1, col_y=2, col_nome=0, col_z=3, col_codigo=4)
    proj = ler("TXT", dados, UTM22S, cfg)
    pts = _pontos(proj)
    assert [p.texto for p in pts] == ["P1", "P2", "P3"]
    for p, (lat, lon) in zip(pts, geo):
        assert p.coords[0, 0] == pytest.approx(lon, abs=1e-8)   # ~1 mm
        assert p.coords[0, 1] == pytest.approx(lat, abs=1e-8)
    assert pts[0].coords[0, 2] == pytest.approx(11.5)
    # código → layer
    assert [p.layer for p in pts] == ["CERCA", "CERCA", "POSTE"]
    assert pts[0].atributos == {"NOME": "P1", "CODIGO": "CERCA"}
    assert proj.camadas["CERCA"].estilo.cor != proj.camadas["POSTE"].estilo.cor


def test_geodesicas_decimais_e_gms_dao_o_mesmo_ponto():
    dec = b"V1;-48,5480;-27,5953\n"
    gms = b"V1;-48,3252800;-27,3543080\n"     # 48°32'52,8" = 48,548 / 27°35'43,08" = 27,5953
    cfg = ConfigTxt(";", False, col_x=1, col_y=2, col_nome=0)
    p_dec = _pontos(ler("TXT", dec, GEO, cfg))[0].coords[0]
    p_gms = _pontos(ler("TXT", gms, GMS, cfg))[0].coords[0]
    assert p_gms[0] == pytest.approx(p_dec[0], abs=1e-9)
    assert p_gms[1] == pytest.approx(p_dec[1], abs=1e-9)


def test_sem_codigo_tudo_em_pontos_e_sem_nome():
    cfg = ConfigTxt(" ", False, col_x=0, col_y=1, col_nome=None)
    proj = ler("TXT", b"712000 6945000\n712010 6945010\n", UTM22S, cfg)
    assert {f.layer for f in proj.feicoes} == {"PONTOS"}
    assert all(f.texto is None for f in proj.feicoes)


@pytest.mark.parametrize("geometria, tipo, n", [("linha", TipoFeicao.LINHA, 4),
                                                 ("poligono", TipoFeicao.POLIGONO, 4)])
def test_liga_pontos_por_layer_na_ordem(geometria, tipo, n):
    texto = ("A;712000;6945000;DIVISA\nB;712100;6945000;DIVISA\nX;712050;6945050;POSTE\n"
             "C;712100;6945100;DIVISA\nD;712000;6945100;DIVISA\nA;712000;6945000;DIVISA\n")
    cfg = ConfigTxt(";", False, col_x=1, col_y=2, col_nome=0, col_codigo=3, geometria=geometria,
                    ligar_por_codigo=True)
    proj = ler("TXT", texto.encode(), UTM22S, cfg)
    ligadas = [f for f in proj.feicoes if f.tipo == tipo]
    assert len(ligadas) == 1 and ligadas[0].layer == "DIVISA"
    # linha mantém o ponto repetido (fecha visualmente); polígono descarta a repetição
    assert len(ligadas[0].coords) == (5 if geometria == "linha" else n)
    assert any("POSTE" in a for a in proj.avisos)      # 1 ponto só: sem linha/polígono
    assert len(_pontos(proj)) == 6
    assert "LIGACAO" not in proj.camadas


def test_liga_todos_os_pontos_na_sequencia_mesmo_com_codigo():
    texto = ("V1;712000;6945000;MARCO\nV2;712100;6945000;PIQUETE\n"
             "V3;712100;6945100;MARCO\nV4;712000;6945100;ARVORE\n")
    cfg = ConfigTxt(";", False, col_x=1, col_y=2, col_nome=0, col_codigo=3,
                    geometria="poligono")             # ligar_por_codigo=False é o padrão
    proj = ler("TXT", texto.encode(), UTM22S, cfg)
    poli = [f for f in proj.feicoes if f.tipo == TipoFeicao.POLIGONO]
    assert len(poli) == 1 and poli[0].layer == "LIGACAO" and len(poli[0].coords) == 4
    # pontos continuam separados por código
    assert {p.layer for p in _pontos(proj)} == {"MARCO", "PIQUETE", "ARVORE"}
    assert not proj.avisos
    # ordem do arquivo preservada: V1 → V2 → V3 → V4
    np.testing.assert_allclose(poli[0].coords[:, :2],
                               [p.coords[0, :2] for p in _pontos(proj)])


def test_sem_codigo_liga_tudo_na_sequencia_mesmo_pedindo_por_codigo():
    cfg = ConfigTxt(" ", False, col_x=0, col_y=1, col_nome=None, geometria="linha",
                    ligar_por_codigo=True)
    proj = ler("TXT", b"712000 6945000\n712010 6945010\n712020 6945000\n", UTM22S, cfg)
    linhas = [f for f in proj.feicoes if f.tipo == TipoFeicao.LINHA]
    assert len(linhas) == 1 and linhas[0].layer == "LIGACAO" and len(linhas[0].coords) == 3


def test_erros_apontam_a_linha():
    cfg = ConfigTxt(";", False, col_x=1, col_y=2, col_nome=0)
    with pytest.raises(ErroLeitura) as ex:
        ler("TXT", b"Nome;E;N\nP1;712000;6945000\nP2;abc;6945000\nP3;712000\n", UTM22S, cfg)
    msg = str(ex.value)
    assert "linha 1" in msg and "linha 3" in msg and "linha 4" in msg
    assert "cabeçalho" in msg


def test_minutos_invalidos_no_gms():
    cfg = ConfigTxt(";", False, col_x=1, col_y=2, col_nome=0)
    with pytest.raises(ErroLeitura, match="linha 1"):
        ler("TXT", b"V1;-48,6252800;-27,3543080\n", GMS, cfg)


def test_sistema_errado_explica():
    cfg = ConfigTxt(";", False, col_x=1, col_y=2, col_nome=0)
    with pytest.raises(ErroLeitura, match="parecem UTM"):
        ler("TXT", b"P1;712000;6945000\n", GEO, cfg)
    with pytest.raises(ErroLeitura, match="parecem geodésicas"):
        ler("TXT", b"P1;-48,5;-27,5\n", UTM22S, cfg)


def test_colunas_iguais_recusadas():
    with pytest.raises(ErroLeitura, match="mesma coluna"):
        ler("TXT", b"1;2\n", UTM22S, ConfigTxt(";", False, col_x=1, col_y=1, col_nome=None))


def test_txt_para_os_tres_formatos_de_saida():
    dados, _ = _arquivo_utm()
    cfg = ConfigTxt(";", True, col_x=1, col_y=2, col_nome=0, col_z=3, col_codigo=4,
                    geometria="linha")
    proj = ler("TXT", dados, UTM22S, cfg)
    for formato, sistema in (("DXF", UTM22S), ("KML", GEO), ("SHP", UTM22S)):
        conteudo, nome = escrever(proj, formato, sistema, "levantamento.txt")
        assert conteudo and nome.startswith("levantamento")
    # DXF de volta: mesmas coordenadas UTM (< 1 mm)
    from core.leitores.dxf import ler_dxf
    volta = ler_dxf(escrever(proj, "DXF", UTM22S, "x")[0], UTM22S)
    a = np.array([p.coords[0, :2] for p in _pontos(proj)])
    b = np.array([p.coords[0, :2] for p in _pontos(volta)])
    assert np.allclose(a, b, atol=1e-8)
