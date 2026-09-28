# ==============================================================================
# Utilitários comuns aos leitores: feições "brutas" no sistema de origem → Projeto.
# ==============================================================================
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.crs import SistemaRef, aviso_fuso, aviso_hemisferio, para_geografico
from core.leitores import ErroLeitura
from core.modelo import Camada, Estilo, Feicao, Projeto, TipoFeicao

M_POR_GRAU = 111_320.0


@dataclass
class Bruta:
    """Feição ainda no sistema de origem (x, y, z)."""
    tipo: TipoFeicao
    pts: list                        # [(x, y, z), ...]
    layer: str
    estilo: Estilo | None = None
    texto: str | None = None
    atributos: dict = field(default_factory=dict)


def remover_fechamento(pts: list) -> list:
    """Polígono guardado sem repetir o 1º vértice no fim."""
    if len(pts) > 3 and np.allclose(pts[0][:2], pts[-1][:2], rtol=0, atol=1e-12):
        return pts[:-1]
    return pts


def _faixa_valida(sistema: SistemaRef, xy: np.ndarray) -> np.ndarray:
    x, y = xy[:, 0], xy[:, 1]
    if sistema.tipo == "GEO":
        return (np.abs(x) <= 180) & (np.abs(y) <= 90)
    return (x > 100_000) & (x < 900_000) & (y > -100) & (y < 10_000_100)


def conferir_sistema(sistema: SistemaRef, xy: np.ndarray, origem: str) -> None:
    """Erro claro quando o sistema informado não combina com os números do arquivo."""
    mx, my = np.median(np.abs(xy[:, 0])), np.median(np.abs(xy[:, 1]))
    parece_geo = mx <= 180 and my <= 90
    if sistema.tipo == "GEO" and not parece_geo:
        valor = f"{mx:,.0f}".replace(",", ".")
        raise ErroLeitura(
            f"As coordenadas do {origem} parecem UTM (valores em metros, como "
            f"E = {valor}). Escolha UTM no sistema de entrada e informe fuso e hemisfério.")
    if sistema.tipo == "UTM" and parece_geo:
        raise ErroLeitura(
            f"As coordenadas do {origem} parecem geodésicas (graus). "
            "Escolha “Geodésicas” no sistema de entrada.")


def montar_projeto(sistema: SistemaRef, brutas: list[Bruta], camadas: dict[str, Camada],
                   origem: str) -> Projeto:
    if not brutas:
        raise ErroLeitura(f"Nenhuma feição reconhecida no {origem}.")
    todos = np.array([p for b in brutas for p in b.pts], dtype=np.float64)
    conferir_sistema(sistema, todos, origem)

    proj = Projeto(sistema)
    descartadas = 0
    validas = []
    for b in brutas:
        xyz = np.asarray(b.pts, dtype=np.float64)
        if not _faixa_valida(sistema, xyz).all():
            descartadas += 1
            continue
        validas.append((b, xyz))
    if not validas:
        x, y = (f"{v:,.0f}".replace(",", ".") for v in np.median(todos[:, :2], axis=0))
        raise ErroLeitura(
            f"As {len(brutas)} feições do {origem} foram lidas, mas nenhuma coordenada cabe em "
            f"{sistema.descricao} (valores típicos: X = {x}, Y = {y}). O arquivo parece estar "
            "em outro sistema de coordenadas — reprojete para UTM SIRGAS 2000 ou geodésicas "
            "(no QGIS: Exportar → Salvar feições como, escolhendo o SRC) e importe de novo.")

    # conversão numa passada só
    tudo = np.concatenate([xyz for _, xyz in validas])
    lon, lat = para_geografico(sistema, tudo[:, 0], tudo[:, 1])
    i = 0
    for b, xyz in validas:
        n = len(xyz)
        c = np.column_stack([lon[i:i + n], lat[i:i + n], xyz[:, 2]])
        i += n
        if not np.any(c[:, 2]):
            c = c[:, :2]
        if b.layer not in camadas:
            camadas[b.layer] = Camada(b.layer)
        proj.camadas.setdefault(b.layer, camadas[b.layer])
        proj.feicoes.append(Feicao(b.tipo, c, b.layer, b.estilo, b.texto or None, b.atributos))

    if descartadas:
        proj.avisos.append(f"{descartadas} feição(ões) com coordenadas fora da faixa de "
                           f"{sistema.descricao} foram ignoradas (ex.: objetos soltos na "
                           "origem 0,0 do desenho).")
    for a in (aviso_hemisferio(sistema, lat), aviso_fuso(sistema, lon)):
        if a:
            proj.avisos.append(a)
    return proj
