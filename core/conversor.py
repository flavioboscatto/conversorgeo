# ==============================================================================
# Ponto único de entrada do núcleo: ler(formato, bytes) → Projeto; escrever(...) → bytes.
# ==============================================================================
from __future__ import annotations

import re

from core.crs import SistemaRef
from core.escritores.dxf import escrever_dxf
from core.escritores.kml import escrever_kml
from core.escritores.shp import escrever_shp
from core.leitores import ErroLeitura
from core.leitores.dxf import ler_dxf
from core.leitores.kml import ler_kml
from core.leitores.shp import ler_shp
from core.leitores.sigef import ler_sigef
from core.modelo import Projeto

FORMATOS_ENTRADA = {
    "DXF": "DXF",
    "KML": "KML / KMZ",
    "SHP": "Shapefile (.zip)",
    "SIGEF": "Planilha SIGEF (.ods)",
}
FORMATOS_SAIDA = {
    "DXF": "DXF",
    "KML": "KML / KMZ",
    "SHP": "Shapefile (.zip)",
}
EXTENSOES = {"DXF": ".dxf", "KML": ".kml,.kmz", "SHP": ".zip", "SIGEF": ".ods"}
SO_GEODESICOS = {"KML"}          # KML é sempre geodésico: nunca UTM
SISTEMA_DO_ARQUIVO = {"SIGEF"}   # sistema vem de dentro do arquivo


def ler(formato: str, dados: bytes, sistema: SistemaRef) -> Projeto:
    """`sistema` é usado no DXF e no Shapefile sem .prj; ignorado nos demais."""
    if not dados:
        raise ErroLeitura("O arquivo está vazio.")
    if formato == "DXF":
        return ler_dxf(dados, sistema)
    if formato == "KML":
        return ler_kml(dados)
    if formato == "SHP":
        return ler_shp(dados, sistema)
    if formato == "SIGEF":
        return ler_sigef(dados)
    raise ErroLeitura(f"Formato de entrada desconhecido: {formato}")


def nome_seguro(nome: str) -> str:
    base = re.sub(r"\.[^.]+$", "", nome or "")
    return re.sub(r"[^\w\-]+", "_", base).strip("_") or "convertido"


def escrever(proj: Projeto, formato: str, sistema: SistemaRef, nome_base: str,
             kmz: bool = True) -> tuple[bytes, str]:
    """Retorna (conteúdo, nome do arquivo para download)."""
    base = nome_seguro(nome_base)
    if formato == "KML":
        if sistema.tipo != "GEO":
            raise ValueError("KML só aceita coordenadas geodésicas.")
        return escrever_kml(proj, kmz=kmz, nome_doc=base), f"{base}.{'kmz' if kmz else 'kml'}"
    if formato == "SHP":
        return escrever_shp(proj, sistema, base), f"{base}_shp.zip"
    if formato == "DXF":
        return escrever_dxf(proj, sistema), f"{base}.dxf"
    raise ValueError(f"Formato de saída desconhecido: {formato}")
