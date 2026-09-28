# ==============================================================================
# Mapa (Leaflet do NiceGUI) com fundo Esri World Imagery, rótulos Esri opcionais e
# exportação da vista atual em PNG/JPG (croqui de localização), feita no navegador.
# As feições vão ao navegador como GeoJSON, uma camada Leaflet por layer.
# ==============================================================================
from __future__ import annotations

import html
import json

from nicegui import ui

from core.modelo import Projeto, TipoFeicao

ESRI_URL = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}")
ESRI_CREDITO = "Imagens &copy; Esri, Maxar, Earthstar Geographics"
LIMITE_ROTULOS_FIXOS = 300      # acima disso, rótulo só ao passar o mouse
PX_POR_MM = 4.0

_CABECALHO = """
<style>
.cg-rotulo { color:#fff; font:600 12px/1.2 Roboto, sans-serif; white-space:nowrap;
             text-shadow:0 0 3px #000, 0 0 2px #000; }
.leaflet-tooltip.cg-tooltip { background:transparent; border:0; box-shadow:none; padding:0;
             color:#fff; font:600 12px/1.2 Roboto, sans-serif;
             text-shadow:0 0 3px #000, 0 0 2px #000; }
.leaflet-tooltip.cg-tooltip::before { display:none; }
.cg-popup td { padding:1px 6px 1px 0; vertical-align:top; }
</style>
<script>
window.cgGrupos = window.cgGrupos || {};
window.cgRotulos = window.cgRotulos || {};
const CG_ESRI_REF = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/';

window.cgMostrar = function (id, dados, enquadrar) {
  const map = getElement(id).map;
  Object.values(window.cgGrupos[id] || {}).forEach(g => map.removeLayer(g));
  const grupos = {};
  const limites = L.latLngBounds([]);
  for (const c of dados.camadas) {
    const g = L.geoJSON(c.geojson, {
      style: f => ({color: f.properties.cor, weight: f.properties.peso, opacity: 1, fillOpacity: 0.12}),
      pointToLayer: (f, ll) => f.properties.tipo === 'texto'
        ? L.marker(ll, {icon: L.divIcon({className: 'cg-rotulo', html: f.properties.html, iconSize: null})})
        : L.circleMarker(ll, {radius: 5, color: '#000', weight: 1, fillColor: f.properties.cor, fillOpacity: 1}),
      onEachFeature: (f, l) => {
        if (f.properties.rotulo) l.bindTooltip(f.properties.rotulo,
            {permanent: dados.rotulos_fixos, direction: 'right', offset: [6, 0], className: 'cg-tooltip'});
        if (f.properties.popup) l.bindPopup(f.properties.popup, {maxWidth: 380});
      },
    });
    if (!(dados.ocultas || []).includes(c.nome)) g.addTo(map);
    grupos[c.nome] = g;
    const b = g.getBounds();
    if (b.isValid()) limites.extend(b);
  }
  window.cgGrupos[id] = grupos;
  if (enquadrar && limites.isValid()) map.fitBounds(limites, {padding: [30, 30], maxZoom: 20});
};

window.cgLimpar = function (id) {
  const map = getElement(id).map;
  Object.values(window.cgGrupos[id] || {}).forEach(g => map.removeLayer(g));
  window.cgGrupos[id] = {};
};

window.cgAlternar = function (id, nome, visivel) {
  const map = getElement(id).map;
  const g = (window.cgGrupos[id] || {})[nome];
  if (!g) return;
  if (visivel) g.addTo(map); else map.removeLayer(g);
};

window.cgRotulosEsri = function (id, ligado) {
  const map = getElement(id).map;
  if (!window.cgRotulos[id]) {
    const op = {maxZoom: 21, maxNativeZoom: 19, crossOrigin: 'anonymous',
                attribution: 'Rótulos &copy; Esri'};
    window.cgRotulos[id] = L.layerGroup([
      L.tileLayer(CG_ESRI_REF + 'World_Transportation/MapServer/tile/{z}/{y}/{x}', op),
      L.tileLayer(CG_ESRI_REF + 'World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', op),
    ]);
  }
  if (ligado) window.cgRotulos[id].addTo(map); else map.removeLayer(window.cgRotulos[id]);
};

// Seta de norte (superior esquerdo, abaixo do zoom) e escala em barra (inferior direito).
window.cgPreparar = function (id) {
  const map = getElement(id).map;
  if (map._cgPreparado) return;
  map._cgPreparado = true;
  const Norte = L.Control.extend({
    onAdd: () => {
      const d = L.DomUtil.create('div', 'cg-norte');
      d.innerHTML = '<svg width="34" height="46" viewBox="0 0 34 46">' +
        '<text x="17" y="12" text-anchor="middle" font="bold" font-size="13" font-weight="700" ' +
        'fill="#fff" stroke="#000" stroke-width="3" paint-order="stroke">N</text>' +
        '<polygon points="17,15 27,44 17,37" fill="#000" stroke="#fff" stroke-width="1"/>' +
        '<polygon points="17,15 7,44 17,37" fill="#fff" stroke="#000" stroke-width="1"/></svg>';
      return d;
    },
  });
  new Norte({position: 'topleft'}).addTo(map);
  L.control.scale({position: 'bottomright', metric: true, imperial: false, maxWidth: 150}).addTo(map);
};

function cgEscalaBonita(maxMetros) {
  const p = Math.pow(10, Math.floor(Math.log10(maxMetros)));
  for (const f of [5, 2, 1]) if (f * p <= maxMetros) return f * p;
  return p;
}

function cgDesenharNorte(ctx, x, y) {
  ctx.save();
  ctx.translate(x, y);
  ctx.font = '700 13px Roboto, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  ctx.lineWidth = 3; ctx.strokeStyle = '#000'; ctx.strokeText('N', 17, 12);
  ctx.fillStyle = '#fff'; ctx.fillText('N', 17, 12);
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(17, 15); ctx.lineTo(27, 44); ctx.lineTo(17, 37); ctx.closePath();
  ctx.fillStyle = '#000'; ctx.fill(); ctx.strokeStyle = '#fff'; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(17, 15); ctx.lineTo(7, 44); ctx.lineTo(17, 37); ctx.closePath();
  ctx.fillStyle = '#fff'; ctx.fill(); ctx.strokeStyle = '#000'; ctx.stroke();
  ctx.restore();
}

function cgDesenharEscala(map, ctx, w, h) {
  const y = h / 2;
  const mPorPx = map.distance(map.containerPointToLatLng([0, y]),
                              map.containerPointToLatLng([100, y])) / 100;
  const metros = cgEscalaBonita(mPorPx * 140);
  const px = metros / mPorPx;
  const texto = metros >= 1000 ? (metros / 1000).toLocaleString('pt-BR') + ' km'
                               : metros.toLocaleString('pt-BR') + ' m';
  const x0 = w - px - 18, y0 = h - 34;
  ctx.fillStyle = 'rgba(255,255,255,0.85)';
  ctx.fillRect(x0 - 8, y0 - 18, px + 16 + 30, 30);
  for (let i = 0; i < 4; i++) {
    ctx.fillStyle = i % 2 ? '#fff' : '#000';
    ctx.fillRect(x0 + i * px / 4, y0, px / 4, 6);
  }
  ctx.strokeStyle = '#000'; ctx.lineWidth = 1; ctx.strokeRect(x0, y0, px, 6);
  ctx.fillStyle = '#000'; ctx.font = '11px Roboto, sans-serif';
  ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'center';
  ctx.fillText('0', x0, y0 - 4);
  ctx.fillText(texto, x0 + px, y0 - 4);
  ctx.textAlign = 'left';
}

// Feições desenhadas a partir das coordenadas (latLngToContainerPoint), no mesmo lugar da tela.
function cgDesenharFeicoes(map, id, ctx) {
  const pt = ll => map.latLngToContainerPoint(ll);
  const aneis = x => (x.length && Array.isArray(x[0])) ? x : [x];
  for (const g of Object.values(window.cgGrupos[id] || {})) {
    if (!map.hasLayer(g)) continue;
    g.eachLayer(l => {
      const o = l.options;
      if (l instanceof L.CircleMarker) {
        const p = pt(l.getLatLng());
        ctx.beginPath(); ctx.arc(p.x, p.y, o.radius, 0, 2 * Math.PI);
        ctx.fillStyle = o.fillColor; ctx.globalAlpha = o.fillOpacity; ctx.fill();
        ctx.globalAlpha = 1; ctx.lineWidth = o.weight; ctx.strokeStyle = o.color; ctx.stroke();
      } else if (l instanceof L.Polyline) {
        const fechado = l instanceof L.Polygon;
        ctx.beginPath();
        for (const anel of aneis(l.getLatLngs())) {
          anel.forEach((ll, i) => { const p = pt(ll); i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); });
          if (fechado) ctx.closePath();
        }
        if (fechado) { ctx.fillStyle = o.color; ctx.globalAlpha = o.fillOpacity; ctx.fill(); }
        ctx.globalAlpha = o.opacity; ctx.lineWidth = o.weight; ctx.strokeStyle = o.color;
        ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.stroke(); ctx.globalAlpha = 1;
      }
    });
  }
}

// Monta a imagem da vista atual: tiles (fundo e rótulos Esri), feições, rótulos das
// feições, seta de norte, escala e o crédito da Esri. Só entra o que está visível no mapa.
window.cgExportar = async function (id, formato, nome) {
  try {
    const map = getElement(id).map;
    const el = map.getContainer();
    const r0 = el.getBoundingClientRect();
    const esc = Math.max(2, window.devicePixelRatio || 1);
    const cv = document.createElement('canvas');
    cv.width = Math.round(r0.width * esc);
    cv.height = Math.round(r0.height * esc);
    const ctx = cv.getContext('2d');
    ctx.scale(esc, esc);
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, r0.width, r0.height);

    for (const img of el.querySelectorAll('.leaflet-tile-pane img.leaflet-tile-loaded')) {
      const r = img.getBoundingClientRect();
      ctx.drawImage(img, r.left - r0.left, r.top - r0.top, r.width, r.height);
    }
    cgDesenharFeicoes(map, id, ctx);
    ctx.font = '600 12px Roboto, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.lineJoin = 'round';
    for (const t of el.querySelectorAll('.leaflet-tooltip.cg-tooltip, .cg-rotulo')) {
      const r = t.getBoundingClientRect();
      const x = r.left - r0.left, y = r.top - r0.top + r.height / 2;
      if (x > r0.width || y > r0.height || x + r.width < 0 || y < 0) continue;
      ctx.lineWidth = 3; ctx.strokeStyle = '#000'; ctx.strokeText(t.innerText, x, y);
      ctx.fillStyle = '#fff'; ctx.fillText(t.innerText, x, y);
    }
    cgDesenharNorte(ctx, 12, 12);
    cgDesenharEscala(map, ctx, r0.width, r0.height);
    const credito = (map.hasLayer(window.cgRotulos[id] || L.layerGroup()) ?
      'Imagens e rótulos' : 'Imagens') + ' © Esri, Maxar, Earthstar Geographics';
    ctx.font = '11px Roboto, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    const w = ctx.measureText(credito).width + 10;
    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.fillRect(r0.width - w, r0.height - 16, w, 16);
    ctx.fillStyle = '#333';
    ctx.fillText(credito, r0.width - w + 5, r0.height - 8);

    const tipo = formato === 'jpg' ? 'image/jpeg' : 'image/png';
    const blob = await new Promise(res => cv.toBlob(res, tipo, 0.92));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = nome;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    return 'ok';
  } catch (e) {
    return String(e);
  }
};
</script>
"""


def instalar() -> None:
    """Estilos e funções JS do mapa (uma vez por página)."""
    ui.add_head_html(_CABECALHO)


def cor_hex(cor) -> str:
    return "#%02x%02x%02x" % tuple(cor)


def hex_para_rgb(texto: str) -> tuple[int, int, int] | None:
    t = (texto or "").strip().lstrip("#")
    if len(t) != 6:
        return None
    try:
        return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)
    except ValueError:
        return None


def _popup(f) -> str:
    linhas = [f"<tr><td><b>Layer</b></td><td>{html.escape(f.layer)}</td></tr>"]
    if f.texto:
        linhas.append(f"<tr><td><b>Texto</b></td><td>{html.escape(f.texto)}</td></tr>")
    for k, v in f.atributos.items():
        if v not in ("", None):
            linhas.append(f"<tr><td><b>{html.escape(str(k))}</b></td>"
                          f"<td>{html.escape(str(v))}</td></tr>")
    return f'<table class="cg-popup">{"".join(linhas)}</table>'


def geojson_do_projeto(proj: Projeto) -> dict:
    por_layer: dict[str, list] = {}
    rotulos = 0
    for f in proj.feicoes:
        est = proj.estilo_de(f)
        c = f.coords[:, :2].tolist()
        if f.tipo in (TipoFeicao.PONTO, TipoFeicao.TEXTO):
            geom = {"type": "Point", "coordinates": c[0]}
        elif f.tipo == TipoFeicao.LINHA:
            geom = {"type": "LineString", "coordinates": c}
        else:
            geom = {"type": "Polygon", "coordinates": [c + [c[0]]]}
        props = {"tipo": f.tipo.value, "cor": cor_hex(est.cor),
                 "peso": max(2.0, est.espessura * PX_POR_MM), "popup": _popup(f)}
        if f.tipo == TipoFeicao.TEXTO:
            props["html"] = html.escape(f.texto or "")
        elif f.tipo == TipoFeicao.PONTO and f.texto:
            props["rotulo"] = html.escape(f.texto)
            rotulos += 1
        por_layer.setdefault(f.layer, []).append(
            {"type": "Feature", "geometry": geom, "properties": props})

    # polígonos por baixo, pontos e textos por cima
    ordem = {"poligono": 0, "linha": 1, "texto": 2, "ponto": 3}
    camadas = sorted(por_layer.items(),
                     key=lambda kv: min(ordem[x["properties"]["tipo"]] for x in kv[1]))
    return {"rotulos_fixos": rotulos <= LIMITE_ROTULOS_FIXOS,
            "camadas": [{"nome": n, "geojson": {"type": "FeatureCollection", "features": fs}}
                        for n, fs in camadas]}


class Mapa:
    def __init__(self):
        self.leaflet = ui.leaflet(center=(-15.8, -47.9), zoom=4, options={"maxZoom": 21}) \
            .classes("w-full h-[560px] rounded")
        self.leaflet.clear_layers()
        self.leaflet.tile_layer(url_template=ESRI_URL, options={
            "maxZoom": 21, "maxNativeZoom": 19, "attribution": ESRI_CREDITO,
            "crossOrigin": "anonymous"})       # necessário para exportar a imagem
        self.leaflet.on("init", lambda: self._js(f"cgPreparar({self.leaflet.id})"))

    def _js(self, codigo: str, timeout: float = 1.0):
        # Pelo cliente do mapa, não pelo contexto do evento: o elemento que disparou a ação
        # (ex.: o seletor de cor do painel de layers) pode já ter sido apagado.
        return self.leaflet.client.run_javascript(codigo, timeout=timeout)

    async def mostrar(self, proj: Projeto, enquadrar: bool = True,
                      ocultas: set[str] | None = None) -> None:
        await self.leaflet.initialized()
        dados = geojson_do_projeto(proj)
        dados["ocultas"] = sorted(ocultas or ())
        await self._js(f"cgMostrar({self.leaflet.id}, {json.dumps(dados, ensure_ascii=False)}, "
                       f"{'true' if enquadrar else 'false'})", timeout=30)

    def limpar(self) -> None:
        """Remove as feições do mapa (a imagem de fundo e o zoom continuam)."""
        self._js(f"cgLimpar({self.leaflet.id})")

    def alternar(self, nome: str, visivel: bool) -> None:
        self._js(f"cgAlternar({self.leaflet.id}, {json.dumps(nome)}, "
                 f"{'true' if visivel else 'false'})")

    async def rotulos_esri(self, ligado: bool) -> None:
        await self.leaflet.initialized()
        self._js(f"cgRotulosEsri({self.leaflet.id}, {'true' if ligado else 'false'})")

    async def exportar_imagem(self, formato: str, nome: str) -> str:
        """Baixa a vista atual como PNG/JPG. Retorna 'ok' ou a mensagem de erro do navegador."""
        await self.leaflet.initialized()
        return await self._js(
            f"cgExportar({self.leaflet.id}, {json.dumps(formato)}, {json.dumps(nome)})",
            timeout=60)
