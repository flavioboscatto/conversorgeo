# ==============================================================================
# Modelo interno único do conversor.
# Coordenadas SEMPRE em SIRGAS 2000 geográfico, float64, colunas (lon, lat[, h]).
# ==============================================================================
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

import numpy as np

from core.crs import SistemaRef


class TipoFeicao(str, Enum):
    PONTO = "ponto"
    LINHA = "linha"
    POLIGONO = "poligono"
    TEXTO = "texto"


@dataclass
class Estilo:
    cor: tuple[int, int, int] = (255, 255, 255)   # RGB 0–255
    espessura: float = 1.0                         # mm (lineweight do CAD)
    tipo_linha: str = "CONTINUOUS"

    def __post_init__(self):
        if len(self.cor) != 3 or any(not 0 <= int(c) <= 255 for c in self.cor):
            raise ValueError(f"Cor RGB inválida: {self.cor}")
        self.cor = tuple(int(c) for c in self.cor)


@dataclass
class Feicao:
    tipo: TipoFeicao
    coords: np.ndarray                     # (n, 2) ou (n, 3): lon, lat[, h]
    layer: str = "0"
    estilo: Estilo | None = None           # None = usa o estilo da camada
    texto: str | None = None
    atributos: dict = field(default_factory=dict)

    def __post_init__(self):
        self.tipo = TipoFeicao(self.tipo)
        c = np.asarray(self.coords, dtype=np.float64)
        if c.ndim == 1:
            c = c.reshape(1, -1)
        if c.ndim != 2 or c.shape[1] not in (2, 3) or c.shape[0] == 0:
            raise ValueError(f"Coordenadas devem ter forma (n, 2) ou (n, 3); veio {c.shape}")
        minimo = {TipoFeicao.PONTO: 1, TipoFeicao.TEXTO: 1,
                  TipoFeicao.LINHA: 2, TipoFeicao.POLIGONO: 3}[self.tipo]
        if c.shape[0] < minimo:
            raise ValueError(f"{self.tipo.value} precisa de pelo menos {minimo} vértice(s)")
        self.coords = c

    @property
    def tem_z(self) -> bool:
        return self.coords.shape[1] == 3


@dataclass
class Camada:
    nome: str
    estilo: Estilo = field(default_factory=Estilo)
    visivel: bool = True


@dataclass
class Projeto:
    crs_origem: SistemaRef
    feicoes: list[Feicao] = field(default_factory=list)
    camadas: dict[str, Camada] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)   # mensagens para o usuário

    def adicionar(self, feicao: Feicao) -> None:
        """Acrescenta a feição, criando a camada se ainda não existir."""
        if feicao.layer not in self.camadas:
            self.camadas[feicao.layer] = Camada(feicao.layer)
        self.feicoes.append(feicao)

    def estilo_de(self, feicao: Feicao) -> Estilo:
        return feicao.estilo or self.camadas[feicao.layer].estilo

    def resumo(self) -> dict[str, int]:
        """Contagem de feições por tipo (para o painel da interface)."""
        cont = {t.value: 0 for t in TipoFeicao}
        for f in self.feicoes:
            cont[f.tipo.value] += 1
        return cont


def juntar(partes: list[tuple[str, Projeto]]) -> Projeto:
    """Soma vários projetos (todos já em SIRGAS 2000 geodésico) num só, para saída única.

    `partes` = [(prefixo, projeto), ...] na ordem de importação. Uma layer que já veio de
    um arquivo anterior ganha o prefixo do arquivo atual (ex.: "lote2_DIVISA").
    As coordenadas não são copiadas.
    """
    if not partes:
        raise ValueError("Nenhum projeto para juntar.")
    total = Projeto(partes[0][1].crs_origem)
    for prefixo, p in partes:
        nomes = {}
        for nome, cam in p.camadas.items():
            novo, k = nome, 2
            if novo in total.camadas:
                novo = f"{prefixo}_{nome}"
                while novo in total.camadas:
                    novo, k = f"{prefixo}_{nome}_{k}", k + 1
            nomes[nome] = novo
            total.camadas[novo] = cam if novo == nome else replace(cam, nome=novo)
        for f in p.feicoes:
            novo = nomes.get(f.layer, f.layer)
            if novo not in total.camadas:
                total.camadas[novo] = Camada(novo)
            total.feicoes.append(f if novo == f.layer else replace(f, layer=novo))
        total.avisos += [f"{prefixo}: {a}" for a in p.avisos]
    return total


def recolorir(proj: Projeto, layer: str, cor: tuple[int, int, int]) -> None:
    """Troca a cor de uma layer (camada e feições com estilo próprio), vale para mapa e saídas.

    Substitui os objetos em vez de alterá-los: camadas e feições podem ser compartilhadas
    com os projetos originais de cada arquivo importado (ver `juntar`).
    """
    cam = proj.camadas[layer]
    proj.camadas[layer] = replace(cam, estilo=replace(cam.estilo, cor=cor))
    proj.feicoes = [replace(f, estilo=replace(f.estilo, cor=cor))
                    if f.layer == layer and f.estilo is not None else f
                    for f in proj.feicoes]
