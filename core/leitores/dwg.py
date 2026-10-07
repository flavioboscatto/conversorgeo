# ==============================================================================
# Leitor DWG (só entrada): DWG → DXF pelo `dwg2dxf` do GNU LibreDWG (GPLv3, programa
# separado, sem modificação) → leitor DXF do projeto.
#   - Render/Docker: binário compilado no Dockerfile (/usr/local/bin/dwg2dxf).
#   - Windows (desenvolvimento): ferramentas/libredwg/dwg2dxf.exe (fora do git).
#   - Ou a variável de ambiente DWG2DXF com o caminho do executável.
# O arquivo vem de qualquer pessoa: a conversão roda em processo próprio, com limite de
# tempo e de memória, numa pasta temporária apagada em seguida (em RAM no Linux, /dev/shm).
# ==============================================================================
from __future__ import annotations

import codecs
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ezdxf.tools.codepage import toencoding

from core.crs import SistemaRef
from core.leitores import ErroLeitura
from core.leitores.dxf import ler_dxf
from core.modelo import Projeto

log = logging.getLogger(__name__)

TEMPO_MAX_S = 60
MEMORIA_MAX_MB = 256          # do processo de conversão (o Render Free tem 512 MB no total)
DXF_MAX_MB = 80               # DXF gerado acima disso não é lido (app não é para arquivos grandes)
# versões aceitas: R13 até o formato 2018 (o mais novo que o LibreDWG lê)
VERSOES = {"AC1012": "R13", "AC1014": "R14", "AC1015": "2000", "AC1018": "2004",
           "AC1021": "2007", "AC1024": "2010", "AC1027": "2013", "AC1032": "2018"}
_LOCAL = Path(__file__).resolve().parents[2] / "ferramentas" / "libredwg" / "dwg2dxf.exe"


def executavel() -> str | None:
    """Caminho do dwg2dxf, ou None se não houver neste computador/servidor."""
    candidatos = [os.environ.get("DWG2DXF", ""), shutil.which("dwg2dxf") or "", str(_LOCAL)]
    return next((c for c in candidatos if c and Path(c).is_file()), None)


def versao_dwg(dados: bytes) -> str:
    """Versão pelo cabeçalho (6 primeiros bytes, ex.: AC1032); erro claro se não for DWG."""
    cab = dados[:6].decode("ascii", errors="replace")
    if not cab.startswith("AC1"):
        raise ErroLeitura("O arquivo não parece ser um DWG. Confira o formato escolhido na "
                          "entrada.")
    if cab not in VERSOES:
        if cab > max(VERSOES):
            raise ErroLeitura(f"DWG em versão mais nova que a suportada ({cab}). No AutoCAD, "
                              "salve como DWG 2018 ou como DXF e importe de novo.")
        raise ErroLeitura(f"DWG em versão muito antiga ({cab}). No CAD, salve como DXF e "
                          "importe de novo.")
    return VERSOES[cab]


def _limitar_recursos():          # roda no processo filho, só em Linux
    import resource
    limite = MEMORIA_MAX_MB * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limite, limite))
    resource.setrlimit(resource.RLIMIT_CPU, (TEMPO_MAX_S, TEMPO_MAX_S))


def _converter(dados: bytes, exe: str) -> bytes:
    pasta_ram = "/dev/shm" if os.path.isdir("/dev/shm") else None
    with tempfile.TemporaryDirectory(prefix="cg_dwg_", dir=pasta_ram) as tmp:
        entrada, saida = Path(tmp, "entrada.dwg"), Path(tmp, "saida.dxf")
        entrada.write_bytes(dados)
        extra = {}
        if sys.platform == "win32":
            extra["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            extra["preexec_fn"] = _limitar_recursos
        try:
            r = subprocess.run([exe, "-y", "-v0", "-o", str(saida), str(entrada)],
                               capture_output=True, timeout=TEMPO_MAX_S, cwd=tmp, **extra)
        except subprocess.TimeoutExpired:
            raise ErroLeitura("A conversão do DWG demorou demais. Salve o desenho como DXF "
                              "no CAD e importe o DXF.") from None
        if not saida.is_file() or saida.stat().st_size == 0:
            log.warning("dwg2dxf falhou (código %s): %s", r.returncode,
                        r.stderr[-500:].decode("utf-8", errors="replace"))
            raise ErroLeitura("Não foi possível converter este DWG. Salve o desenho como DXF "
                              "no CAD e importe o DXF.")
        if saida.stat().st_size > DXF_MAX_MB * 1024 * 1024:
            raise ErroLeitura("O desenho é grande demais para o Conversor Geo. Separe as "
                              "layers de interesse num arquivo menor.")
        return saida.read_bytes()


def _unicode_dxf(erro: UnicodeEncodeError):
    return "".join(f"\\U+{ord(c):04X}" for c in erro.object[erro.start:erro.end]), erro.end


codecs.register_error("cg_unicode_dxf", _unicode_dxf)


def corrigir_texto(dxf: bytes) -> bytes:
    """DWG até 2004 vira DXF que se declara em codepage (ex.: ANSI_1252), mas o LibreDWG
    grava os textos em UTF-8 — os acentos sairiam trocados (“Ã\x81rea”). Nesse caso, regrava
    no codepage declarado, com os caracteres especiais no escape do DXF (\\U+00C1).
    DXF 2007+ é sempre UTF-8 e não é tocado; texto que não é UTF-8 válido também não."""
    m = re.search(rb"\$ACADVER\s*\r?\n\s*1\s*\r?\n\s*(AC\d{4})", dxf[:4000])
    if not m or m.group(1) >= b"AC1021" or dxf.isascii():
        return dxf
    try:
        texto = dxf.decode("utf-8")
    except UnicodeDecodeError:
        return dxf                       # já está no codepage declarado
    cp = re.search(rb"\$DWGCODEPAGE\s*\r?\n\s*3\s*\r?\n\s*(\S+)", dxf[:8000])
    cod = toencoding(cp.group(1).decode("ascii", "replace")) if cp else "cp1252"
    return texto.encode(cod, errors="cg_unicode_dxf")


def ler_dwg(dados: bytes, sistema: SistemaRef) -> Projeto:
    versao_dwg(dados)
    exe = executavel()
    if exe is None:
        log.error("dwg2dxf não encontrado: leitura de DWG indisponível")
        raise ErroLeitura("A leitura de DWG está indisponível no momento. Salve o desenho "
                          "como DXF no CAD e importe o DXF.")
    return ler_dxf(corrigir_texto(_converter(dados, exe)), sistema, "DWG")
