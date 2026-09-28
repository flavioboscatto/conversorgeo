"""Testes do MotorGeodesico contra o pyproj (referência de conferência — Etapa 0).

Aceite: diferença motor × pyproj < 1 mm em E/N e < 0,00001" em lat/lon.
"""
import math

import pytest
from pyproj import CRS, Proj, Transformer

from core.geodesia.motor_geodesico import MotorGeodesico as MG

TOL_M = 0.001                       # 1 mm
TOL_GRAUS = 0.00001 / 3600.0        # 0,00001" em graus

# (fuso, EPSG UTM Sul, lista de (lat, lon)) — pontos no MC, a ~1,5° e a ~3° do MC
CASOS = [
    (22, 31982, [(-27.5953, -48.5480),   # Florianópolis (2,45° a leste do MC -51°)
                 (-26.3045, -48.8487),   # Joinville
                 (-27.0000, -51.0000),   # sobre o MC
                 (-29.1678, -51.1794),   # Caxias do Sul
                 (-25.0000, -53.9000)]), # ~2,9° a oeste do MC
    (23, 31983, [(-23.5505, -46.6333),   # São Paulo
                 (-22.9068, -43.1729),   # Rio de Janeiro
                 (-20.0000, -45.0000),   # sobre o MC
                 (-15.7939, -47.8828)]), # Brasília
]

PONTOS = [(fuso, epsg, lat, lon) for fuso, epsg, pts in CASOS for lat, lon in pts]
IDS = [f"{fuso}S_{lat:.2f}_{lon:.2f}" for fuso, _, lat, lon in PONTOS]


def _ida(epsg):
    return Transformer.from_crs("EPSG:4674", f"EPSG:{epsg}", always_xy=True)


def _volta(epsg):
    return Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4674", always_xy=True)


# ------------------------------------------------------------------ geo → UTM
@pytest.mark.parametrize("fuso,epsg,lat,lon", PONTOS, ids=IDS)
def test_geo_para_utm(fuso, epsg, lat, lon):
    e_ref, n_ref = _ida(epsg).transform(lon, lat)
    e, n = MG.lat_lon_para_utm(lat, lon, fuso, "S")
    assert abs(e - e_ref) < TOL_M, f"dE = {(e - e_ref) * 1000:.4f} mm"
    assert abs(n - n_ref) < TOL_M, f"dN = {(n - n_ref) * 1000:.4f} mm"


# ------------------------------------------------------------------ UTM → geo
@pytest.mark.parametrize("fuso,epsg,lat,lon", PONTOS, ids=IDS)
def test_utm_para_geo(fuso, epsg, lat, lon):
    e, n = _ida(epsg).transform(lon, lat)          # E/N exatos do pyproj
    lon_ref, lat_ref = _volta(epsg).transform(e, n)
    lat_m, lon_m, _, _ = MG.utm_para_lat_lon(e, n, fuso, "S")
    assert abs(lat_m - lat_ref) < TOL_GRAUS, f'dLat = {(lat_m - lat_ref) * 3600:.7f}"'
    assert abs(lon_m - lon_ref) < TOL_GRAUS, f'dLon = {(lon_m - lon_ref) * 3600:.7f}"'


# ------------------------------------------------------------- ida e volta
@pytest.mark.parametrize("fuso,epsg,lat,lon", PONTOS, ids=IDS)
def test_ida_e_volta_motor(fuso, epsg, lat, lon):
    e, n = MG.lat_lon_para_utm(lat, lon, fuso, "S")
    lat2, lon2, _, _ = MG.utm_para_lat_lon(e, n, fuso, "S")
    assert abs(lat2 - lat) < TOL_GRAUS, f'dLat = {(lat2 - lat) * 3600:.7f}"'
    assert abs(lon2 - lon) < TOL_GRAUS, f'dLon = {(lon2 - lon) * 3600:.7f}"'
    e2, n2 = MG.lat_lon_para_utm(lat2, lon2, fuso, "S")
    assert abs(e2 - e) < TOL_M and abs(n2 - n) < TOL_M


# ------------------------------------------- fator de escala e convergência
@pytest.mark.parametrize("fuso,epsg,lat,lon", PONTOS, ids=IDS)
def test_registro_escala_convergencia(fuso, epsg, lat, lon):
    """Só registra (não reprova): 3º e 4º retornos de utm_para_lat_lon × pyproj.

    Rodar com `pytest -s` para ver a tabela de diferenças.
    """
    e, n = _ida(epsg).transform(lon, lat)
    _, _, k_m, conv_m = MG.utm_para_lat_lon(e, n, fuso, "S")
    fat = Proj(f"EPSG:{epsg}").get_factors(lon, lat)
    k_ref, conv_ref = fat.meridional_scale, fat.meridian_convergence
    print(f"\n  {fuso}S lat={lat:9.4f} lon={lon:9.4f} | "
          f"k motor={k_m:.9f} pyproj={k_ref:.9f} dk={k_m - k_ref:+.2e} | "
          f"conv motor={conv_m:+.6f}° pyproj={conv_ref:+.6f}° "
          f'dif={(conv_m - conv_ref) * 3600:+.3f}"')
    assert math.isfinite(k_m) and math.isfinite(conv_m)


# ---------------------------------------------------------- nomes dos EPSG
@pytest.mark.parametrize("fuso", range(17, 26))
def test_epsg_utm_sul(fuso):
    assert CRS.from_epsg(31960 + fuso).name == f"SIRGAS 2000 / UTM zone {fuso}S"


@pytest.mark.parametrize("fuso", range(17, 23))
def test_epsg_utm_norte(fuso):
    assert CRS.from_epsg(31954 + fuso).name == f"SIRGAS 2000 / UTM zone {fuso}N"


def test_epsg_geografico():
    assert CRS.from_epsg(4674).name == "SIRGAS 2000"


# ------------------------------------------- sexagesimal (formato SIGEF)
def _gms(g, m, s, sinal=1.0):
    return sinal * (g + m / 60.0 + s / 3600.0)


@pytest.mark.parametrize("texto,esperado", [
    ("48 32 28,781 W", _gms(48, 32, 28.781, -1)),
    ("27 35 43,092 S", _gms(27, 35, 43.092, -1)),
    ("48 32 28,781 E", _gms(48, 32, 28.781)),
    ("05 10 02,500 N", _gms(5, 10, 2.5)),
    ("48 32 28.781 W", _gms(48, 32, 28.781, -1)),
    ("48°32'28,781\" W", _gms(48, 32, 28.781, -1)),
    ("  48 32 28,781 W  ", _gms(48, 32, 28.781, -1)),
    ("-48 32 28,781", _gms(48, 32, 28.781, -1)),
    ("48 00 00,000 W", -48.0),
])
def test_sexagesimal_para_decimal(texto, esperado):
    assert MG.sexagesimal_para_decimal(texto) == pytest.approx(esperado, abs=1e-12)


@pytest.mark.parametrize("texto", ["", "   ", "W", "abc"])
def test_sexagesimal_invalido(texto):
    with pytest.raises(ValueError):
        MG.sexagesimal_para_decimal(texto)
