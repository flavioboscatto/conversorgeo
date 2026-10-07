"""Leitor DWG (LibreDWG dwg2dxf). Testes de conversão pulados se o dwg2dxf não existir aqui."""
from pathlib import Path

import numpy as np
import pytest

from core.conversor import ler
from core.crs import SistemaRef
from core.leitores import ErroLeitura
from core.leitores import dwg

DADOS = Path(__file__).parent / "dados"
UTM22S = SistemaRef.utm(22, "S")
sem_dwg2dxf = pytest.mark.skipif(dwg.executavel() is None, reason="dwg2dxf não instalado")


@pytest.mark.parametrize("cab, versao", [(b"AC1015", "2000"), (b"AC1032", "2018")])
def test_versao_pelo_cabecalho(cab, versao):
    assert dwg.versao_dwg(cab + b"\x00" * 10) == versao


@pytest.mark.parametrize("dados, trecho", [
    (b"0\nSECTION\n", "não parece ser um DWG"),
    (b"AC1033\x00\x00", "mais nova"),
    (b"AC1009\x00\x00", "muito antiga"),
])
def test_cabecalho_invalido(dados, trecho):
    with pytest.raises(ErroLeitura, match=trecho):
        ler("DWG", dados, UTM22S)


def test_sem_conversor_explica(monkeypatch):
    monkeypatch.setattr(dwg, "executavel", lambda: None)
    with pytest.raises(ErroLeitura, match="Salve o desenho como DXF"):
        ler("DWG", b"AC1032" + b"\x00" * 100, UTM22S)


def test_corrigir_texto_dxf_antigo_em_utf8():
    dxf = ("0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1015\n9\n$DWGCODEPAGE\n3\nANSI_1252\n"
           "0\nENDSEC\n1\nÁrea da União\n").encode("utf-8")
    saida = dwg.corrigir_texto(dxf)
    assert b"\\U+00C1rea da Uni\\U+00E3o" in saida or "Área da União".encode("cp1252") in saida
    # DXF 2007+ (UTF-8 por definição) e texto já em codepage ficam como estão
    novo = dxf.replace(b"AC1015", b"AC1032")
    assert dwg.corrigir_texto(novo) == novo
    em_cp = dxf.decode("utf-8").encode("cp1252")
    assert dwg.corrigir_texto(em_cp) == em_cp


@sem_dwg2dxf
def test_dwg_igual_ao_dxf_de_origem():
    """exemplo_utm22s.dwg foi gerado do exemplo_utm22s.dxf (LibreDWG dxf2dwg, formato 2000)."""
    a = ler("DXF", (DADOS / "exemplo_utm22s.dxf").read_bytes(), UTM22S)
    b = ler("DWG", (DADOS / "exemplo_utm22s.dwg").read_bytes(), UTM22S)
    assert b.resumo() == a.resumo()
    chave = lambda f: (f.tipo.value, f.layer, f.texto or "", float(f.coords[0, 0]))
    fa, fb = sorted(a.feicoes, key=chave), sorted(b.feicoes, key=chave)
    assert [chave(f)[:3] for f in fa] == [chave(f)[:3] for f in fb]     # inclui “Área de teste”
    for x, y in zip(fa, fb):
        assert np.allclose(x.coords[:, :2], y.coords[:, :2], atol=1e-10)  # < 0,01 mm
    assert b.avisos == a.avisos                                     # objeto solto na origem


@sem_dwg2dxf
def test_dwg_corrompido():
    dados = (DADOS / "exemplo_utm22s.dwg").read_bytes()
    with pytest.raises(ErroLeitura):
        ler("DWG", dados[:200], UTM22S)
