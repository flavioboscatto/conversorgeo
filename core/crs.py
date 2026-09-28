# ==============================================================================
# Sistemas de referência e conversões para/de SIRGAS 2000 geográfico.
# Toda a matemática vem do MotorGeodesico (não usar pyproj em produção).
# ==============================================================================
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from core.geodesia.motor_geodesico import MotorGeodesico

EPSG_GEO = 4674
FUSOS_SUL = range(17, 26)      # 17S–25S → 31977–31985
FUSOS_NORTE = range(17, 25)    # 17N–24N (25N não existe no EPSG)
_EPSG_NORTE_ESPECIAL = {23: 6210, 24: 6211}   # 31954+23 = 31977 seria o 17S!
LIMITE_FUSO_GRAUS = 3.0


@dataclass(frozen=True)
class SistemaRef:
    tipo: str                    # "GEO" ou "UTM"
    fuso: int | None = None
    hemisferio: str | None = None   # "N" ou "S"
    gms: bool = False            # GEO: entrada/saída em graus-minutos-segundos

    def __post_init__(self):
        if self.tipo not in ("GEO", "UTM"):
            raise ValueError(f"Tipo de sistema desconhecido: {self.tipo}")
        if self.tipo == "UTM":
            if self.hemisferio not in ("N", "S"):
                raise ValueError("Informe o hemisfério (N ou S) para coordenadas UTM.")
            validos = FUSOS_SUL if self.hemisferio == "S" else FUSOS_NORTE
            if self.fuso not in validos:
                raise ValueError(
                    f"Fuso {self.fuso}{self.hemisferio} fora do intervalo aceito "
                    f"({validos.start}–{validos.stop - 1}{self.hemisferio}).")

    @classmethod
    def geografico(cls, gms: bool = False) -> "SistemaRef":
        return cls("GEO", gms=gms)

    @classmethod
    def utm(cls, fuso: int, hemisferio: str) -> "SistemaRef":
        return cls("UTM", int(fuso), hemisferio.upper())

    @property
    def epsg(self) -> int:
        if self.tipo == "GEO":
            return EPSG_GEO
        if self.hemisferio == "S":
            return 31960 + self.fuso
        return _EPSG_NORTE_ESPECIAL.get(self.fuso, 31954 + self.fuso)

    @property
    def meridiano_central(self) -> float | None:
        return None if self.tipo == "GEO" else self.fuso * 6.0 - 183.0

    @property
    def descricao(self) -> str:
        if self.tipo == "GEO":
            return "SIRGAS 2000 geodésicas" + (" (GMS)" if self.gms else "")
        return f"SIRGAS 2000 / UTM {self.fuso}{self.hemisferio}"


# ------------------------------------------------------------ .prj (WKT ESRI)
_WKT_GEOG = ('GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",'
             'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')


def wkt_prj(sistema: SistemaRef) -> str:
    """Conteúdo do .prj (WKT1 no dialeto ESRI) sem depender do pyproj."""
    if sistema.tipo == "GEO":
        return _WKT_GEOG
    falso_norte = 10000000.0 if sistema.hemisferio == "S" else 0.0
    return (f'PROJCS["SIRGAS_2000_UTM_Zone_{sistema.fuso}{sistema.hemisferio}",{_WKT_GEOG},'
            'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
            f'PARAMETER["False_Northing",{falso_norte}],'
            f'PARAMETER["Central_Meridian",{sistema.meridiano_central}],'
            'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],'
            'UNIT["Meter",1.0]]')


def _parametro_wkt(texto: str, nome: str) -> float | None:
    m = re.search(rf'PARAMETER\["{nome}",\s*(-?[\d.]+(?:E-?\d+)?)', texto)
    return float(m.group(1)) if m else None


def sistema_de_prj(wkt: str) -> tuple[SistemaRef, str | None]:
    """Interpreta um .prj (ESRI ou OGC). Retorna (sistema, aviso de datum ou None).

    Aceita geodésico e UTM (Transverse Mercator com k0 = 0,9996). Levanta ValueError
    para projeções não suportadas.
    """
    t = " ".join(wkt.upper().split())
    aviso = None
    if "SIRGAS" not in t and not ("WGS" in t and "84" in t):
        aviso = ("O .prj indica um datum diferente de SIRGAS 2000/WGS 84. As coordenadas "
                 "foram lidas como SIRGAS 2000 sem transformação de datum — confira.")
    if t.startswith(("PROJCS", "PROJCRS")):
        if "TRANSVERSE_MERCATOR" not in t.replace(" ", "_"):
            raise ValueError("Projeção do .prj não suportada (só UTM ou geodésicas).")
        m = re.search(r"UTM[ _]ZONE[ _](\d{1,2})\s*([NS])", t)
        if m:
            return SistemaRef.utm(int(m.group(1)), m.group(2)), aviso
        mc = _parametro_wkt(t, "CENTRAL_MERIDIAN")
        fn = _parametro_wkt(t, "FALSE_NORTHING") or 0.0
        if mc is None:
            raise ValueError("O .prj não informa o meridiano central.")
        return SistemaRef.utm(round((mc + 183.0) / 6.0), "S" if fn > 0 else "N"), aviso
    if t.startswith(("GEOGCS", "GEOGCRS", "GEODCRS")):
        return SistemaRef.geografico(), aviso
    raise ValueError("Não foi possível interpretar o .prj.")


# ------------------------------------------------------------------ sugestões
def sugerir_fuso(lon: float) -> int:
    """Fuso UTM que contém a longitude (graus decimais)."""
    return int(math.floor((lon + 180.0) / 6.0)) + 1


def sugerir_hemisferio(lat: float) -> str:
    return "S" if lat < 0 else "N"


# ---------------------------------------------------------------- conversões
def _como_array(v) -> np.ndarray:
    return np.atleast_1d(np.asarray(v, dtype=np.float64))


def para_geografico(sistema: SistemaRef, x, y) -> tuple[np.ndarray, np.ndarray]:
    """(x, y) no sistema → (lon, lat) SIRGAS 2000 em graus decimais.

    GEO: x = lon, y = lat.  UTM: x = E, y = N.
    """
    x, y = _como_array(x), _como_array(y)
    if sistema.tipo == "GEO":
        return x.copy(), y.copy()
    lon = np.empty_like(x)
    lat = np.empty_like(y)
    for i in range(x.size):
        lat[i], lon[i], _, _ = MotorGeodesico.utm_para_lat_lon(
            x[i], y[i], sistema.fuso, sistema.hemisferio)
    return lon, lat


def de_geografico(sistema: SistemaRef, lon, lat) -> tuple[np.ndarray, np.ndarray]:
    """(lon, lat) SIRGAS 2000 → (x, y) no sistema."""
    lon, lat = _como_array(lon), _como_array(lat)
    if sistema.tipo == "GEO":
        return lon.copy(), lat.copy()
    e = np.empty_like(lon)
    n = np.empty_like(lat)
    for i in range(lon.size):
        e[i], n[i] = MotorGeodesico.lat_lon_para_utm(
            lat[i], lon[i], sistema.fuso, sistema.hemisferio)
    return e, n


def converter(origem: SistemaRef, destino: SistemaRef, x, y):
    lon, lat = para_geografico(origem, x, y)
    return de_geografico(destino, lon, lat)


# ------------------------------------------------------------ aviso de fuso
def pontos_fora_do_fuso(sistema: SistemaRef, lon) -> np.ndarray:
    """Índices dos pontos a mais de 3° do meridiano central do fuso informado."""
    if sistema.tipo == "GEO":
        return np.array([], dtype=int)
    dist = np.abs(_como_array(lon) - sistema.meridiano_central)
    return np.nonzero(dist > LIMITE_FUSO_GRAUS + 1e-12)[0]


def aviso_hemisferio(sistema: SistemaRef, lat) -> str | None:
    """Mensagem quando há pontos no hemisfério oposto ao informado; senão None."""
    if sistema.tipo == "GEO":
        return None
    lat = _como_array(lat)
    fora = np.count_nonzero(lat > 0) if sistema.hemisferio == "S" else np.count_nonzero(lat < 0)
    if fora == 0:
        return None
    outro = "Norte" if sistema.hemisferio == "S" else "Sul"
    qtd = "1 ponto está" if fora == 1 else f"{fora} pontos estão"
    return (f"Atenção: {qtd} no hemisfério {outro}, mas o sistema informado é "
            f"UTM {sistema.fuso}{sistema.hemisferio}. Confira o hemisfério.")


def aviso_fuso(sistema: SistemaRef, lon) -> str | None:
    """Mensagem para o usuário quando há pontos fora do fuso; senão None."""
    fora = pontos_fora_do_fuso(sistema, lon)
    if fora.size == 0:
        return None
    lon = _como_array(lon)
    sugestao = sugerir_fuso(float(np.median(lon)))
    qtd = "1 ponto está" if fora.size == 1 else f"{fora.size} pontos estão"
    return (f"Atenção: {qtd} a mais de 3° do meridiano central do fuso "
            f"{sistema.fuso}{sistema.hemisferio} ({sistema.meridiano_central:.0f}°). "
            f"Confira o fuso — pela longitude, o fuso provável é {sugestao}.")
