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
.cg-rua { position:absolute; white-space:nowrap; pointer-events:none; color:#fff;
          font:600 12px/1 Roboto, sans-serif; -webkit-text-stroke:3px #000; paint-order:stroke fill; }
.cg-aviso-ruas { background:rgba(255,255,255,.9); padding:2px 8px; border-radius:4px;
                 font:12px Roboto, sans-serif; color:#333; }
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

// ---------------------------------------------------------------- fundo
// 'esri' (padrão) ou 'sc': ortofoto do aerolevantamento de SC 2010–2012 (0,39 m), WMS aberto.
// PNG transparente por cima da Esri: fora de SC a Esri continua aparecendo.
const CG_SC_WMS = 'https://sigsc.sc.gov.br/sigserver/SIGSC/wms';
const CG_SC_CAIXA = [[-29.4785, -54.0992], [-25.8239, -48.1126]];   // L ainda não existe aqui
const CG_SC_CREDITO = 'Ortofotos &copy; SDE/SC (2012)';
window.cgFundos = window.cgFundos || {};

window.cgFundo = function (id, fundo) {
  const map = getElement(id).map;
  let f = window.cgFundos[id];
  if (!f) {
    const Aviso = L.Control.extend({onAdd: () => L.DomUtil.create('div', 'cg-aviso-ruas')});
    f = window.cgFundos[id] = {modo: 'esri', aviso: new Aviso({position: 'topright'}),
      sc: L.tileLayer.wms(CG_SC_WMS, {layers: 'OrtoRGB-Landsat-2012', format: 'image/png',
        transparent: true, version: '1.3.0', crossOrigin: 'anonymous', maxZoom: 21,
        zIndex: 2, attribution: CG_SC_CREDITO})};
    map.on('moveend', () => cgAvisoFundo(id));
  }
  f.modo = fundo;
  if (fundo === 'sc') { f.sc.addTo(map); f.aviso.addTo(map); }
  else { map.removeLayer(f.sc); f.aviso.remove(); }
  cgAvisoFundo(id);
};

function cgAvisoFundo(id) {
  const f = window.cgFundos[id];
  if (!f || f.modo !== 'sc' || !f.aviso.getContainer()) return;
  const fora = !L.latLngBounds(CG_SC_CAIXA).intersects(getElement(id).map.getBounds());
  const el = f.aviso.getContainer();
  el.textContent = fora ? 'Ortofoto SC só cobre Santa Catarina — aqui aparece a imagem Esri' : '';
  el.style.display = fora ? '' : 'none';
}

// ---------------------------------------------------------------- rótulos
// modo: 'nenhum' | 'esri' (tiles de referência da Esri) | 'osm' (só nomes de ruas do
// OpenStreetMap, buscados na Overpass API e escritos ao longo das ruas, sem números)
const CG_OVERPASS = 'https://overpass-api.de/api/interpreter';
const CG_TENTATIVAS = 3;       // o Overpass público oscila (504 em horário de pico)
const CG_ZOOM_MIN_RUAS = 15;
const CG_OSM_CREDITO = 'Ruas &copy; colaboradores do OpenStreetMap';
const CG_FONTE_RUA = '600 12px Roboto, sans-serif';
window.cgRuas = window.cgRuas || {};

window.cgRotulosModo = function (id, modo) {
  const map = getElement(id).map;
  if (!window.cgRotulos[id]) {
    const op = {maxZoom: 21, maxNativeZoom: 19, crossOrigin: 'anonymous', zIndex: 5,
                attribution: 'Rótulos &copy; Esri'};
    window.cgRotulos[id] = L.layerGroup([
      L.tileLayer(CG_ESRI_REF + 'World_Transportation/MapServer/tile/{z}/{y}/{x}', op),
      L.tileLayer(CG_ESRI_REF + 'World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', op),
    ]);
  }
  if (modo === 'esri') window.cgRotulos[id].addTo(map); else map.removeLayer(window.cgRotulos[id]);

  let st = window.cgRuas[id];
  if (!st) {
    st = window.cgRuas[id] = {ativo: false, vias: [], caixa: null, pedindo: false,
                              grupo: L.layerGroup(), aviso: null};
    const Aviso = L.Control.extend({onAdd: () => L.DomUtil.create('div', 'cg-aviso-ruas')});
    st.aviso = new Aviso({position: 'topright'});
    map.on('moveend', () => cgAtualizarRuas(id));
  }
  const ligar = modo === 'osm';
  if (ligar === st.ativo) return;
  st.ativo = ligar;
  if (ligar) {
    st.grupo.addTo(map);
    st.aviso.addTo(map);
    map.attributionControl.addAttribution(CG_OSM_CREDITO);
    cgAtualizarRuas(id);
  } else {
    map.removeLayer(st.grupo);
    st.aviso.remove();
    map.attributionControl.removeAttribution(CG_OSM_CREDITO);
  }
};

function cgAvisoRuas(st, texto) {
  const el = st.aviso.getContainer();
  if (!el) return;
  el.textContent = texto;
  el.style.display = texto ? '' : 'none';
}

async function cgBuscarVias(caixa, aoTentar) {
  const b = [caixa.getSouth(), caixa.getWest(), caixa.getNorth(), caixa.getEast()]
    .map(v => v.toFixed(6)).join(',');
  const tipos = 'motorway|trunk|primary|secondary|tertiary|unclassified|residential|' +
    'living_street|pedestrian|road|service|motorway_link|trunk_link|primary_link|' +
    'secondary_link|tertiary_link';
  const q = `[out:json][timeout:25];way["highway"~"^(${tipos})$"]["name"](${b});out geom;`;
  for (let n = 1; n <= CG_TENTATIVAS; n++) {
    if (aoTentar) aoTentar(n);
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 25000);
      const r = await fetch(CG_OVERPASS, {method: 'POST', signal: ctl.signal,
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: 'data=' + encodeURIComponent(q)});
      clearTimeout(t);
      if (r.ok) {
        const j = await r.json();
        return j.elements.filter(e => e.geometry && e.tags && e.tags.name);
      }
    } catch (e) { /* tempo esgotado ou rede: tenta de novo */ }
    if (n < CG_TENTATIVAS) await new Promise(res => setTimeout(res, 2000 * n));
  }
  throw new Error('Overpass indisponível');
}

async function cgAtualizarRuas(id) {
  const st = window.cgRuas[id];
  if (!st || !st.ativo) return;
  const map = getElement(id).map;
  if (map.getZoom() < CG_ZOOM_MIN_RUAS) {
    st.grupo.clearLayers();
    cgAvisoRuas(st, 'Aproxime o mapa para ver os nomes de ruas');
    return;
  }
  const vista = map.getBounds();
  if (!st.caixa || !st.caixa.contains(vista)) {
    if (st.pedindo) return;
    st.pedindo = true;
    cgAvisoRuas(st, 'Buscando nomes de ruas…');
    try {
      const caixa = vista.pad(0.5);
      st.vias = await cgBuscarVias(caixa, n => cgAvisoRuas(st, n === 1
        ? 'Buscando nomes de ruas…'
        : `Servidor ocupado — tentando de novo (${n} de ${CG_TENTATIVAS})…`));
      st.caixa = caixa;
      cgAvisoRuas(st, '');
    } catch (e) {
      cgAvisoRuas(st, 'Servidor do OpenStreetMap indisponível — mova o mapa para tentar de novo');
      st.pedindo = false;
      return;
    }
    st.pedindo = false;
    if (!st.caixa.contains(map.getBounds())) return cgAtualizarRuas(id);   // mapa andou
  }
  cgDesenharRuasMapa(id);
}

// Posição e ângulo de cada nome, em pixels da vista atual. Mesmo cálculo para tela e imagem.
function cgCalcularRotulosRuas(map, vias) {
  const cv = document.createElement('canvas').getContext('2d');
  cv.font = CG_FONTE_RUA;
  const tam = map.getSize();
  const vista = L.bounds([8, 8], [tam.x - 8, tam.y - 8]);
  const prioridade = {motorway: 0, trunk: 1, primary: 2, secondary: 3, tertiary: 4};
  const ordenadas = [...vias].sort((a, b) =>
    (prioridade[a.tags.highway] ?? 5) - (prioridade[b.tags.highway] ?? 5));
  const colocados = [];
  for (const via of ordenadas) {
    const texto = via.tags.name;
    const larg = cv.measureText(texto).width;
    const todos = via.geometry.map(g => map.latLngToContainerPoint([g.lat, g.lon]));
    // só a parte visível: recorta cada segmento na borda da tela
    const pedacos = [];
    let atual = null;
    for (let k = 0; k < todos.length - 1; k++) {
      const seg = L.LineUtil.clipSegment(todos[k], todos[k + 1], vista, false, false);
      if (!seg) { atual = null; continue; }
      if (atual && atual[atual.length - 1].distanceTo(seg[0]) < 0.01) atual.push(seg[1]);
      else pedacos.push(atual = [seg[0], seg[1]]);
    }
    // trechos quase retos (desvio < 20°) formam uma "corrida"; o nome vai na mais longa
    let melhor = null;
    for (const pts of pedacos) {
      let i = 0;
      while (i < pts.length - 1) {
        let j = i + 1;
        const ang0 = Math.atan2(pts[j].y - pts[i].y, pts[j].x - pts[i].x);
        let comp = pts[i].distanceTo(pts[j]);
        while (j < pts.length - 1) {
          const a = Math.atan2(pts[j + 1].y - pts[j].y, pts[j + 1].x - pts[j].x);
          let d = Math.abs(a - ang0) % (2 * Math.PI);
          if (d > Math.PI) d = 2 * Math.PI - d;
          if (d > 0.35) break;
          comp += pts[j].distanceTo(pts[j + 1]);
          j++;
        }
        if (!melhor || comp > melhor.comp) melhor = {pts, i, j, comp};
        i = j;
      }
    }
    if (!melhor || melhor.comp < larg + 16) continue;
    const pts = melhor.pts;
    // ponto na metade do comprimento da corrida
    let resta = melhor.comp / 2, x = pts[melhor.i].x, y = pts[melhor.i].y;
    for (let k = melhor.i; k < melhor.j; k++) {
      const s = pts[k].distanceTo(pts[k + 1]);
      if (resta <= s) {
        x = pts[k].x + (pts[k + 1].x - pts[k].x) * resta / s;
        y = pts[k].y + (pts[k + 1].y - pts[k].y) * resta / s;
        break;
      }
      resta -= s;
    }
    let ang = Math.atan2(pts[melhor.j].y - pts[melhor.i].y, pts[melhor.j].x - pts[melhor.i].x);
    if (ang > Math.PI / 2) ang -= Math.PI;          // texto sempre de pé
    if (ang < -Math.PI / 2) ang += Math.PI;
    const c = Math.abs(Math.cos(ang)), s = Math.abs(Math.sin(ang));
    const hw = (c * larg + s * 14) / 2, hh = (s * larg + c * 14) / 2;
    if (colocados.some(o => Math.abs(o.x - x) < o.hw + hw + 4 && Math.abs(o.y - y) < o.hh + hh + 4))
      continue;
    if (colocados.some(o => o.texto === texto && Math.hypot(o.x - x, o.y - y) < 250)) continue;
    colocados.push({x, y, ang, texto, hw, hh});
  }
  return colocados;
}

function cgDesenharRuasMapa(id) {
  const st = window.cgRuas[id];
  const map = getElement(id).map;
  st.grupo.clearLayers();
  for (const r of cgCalcularRotulosRuas(map, st.vias)) {
    const d = document.createElement('div');
    d.className = 'cg-rua';
    d.style.transform = `translate(-50%, -50%) rotate(${r.ang}rad)`;
    d.textContent = r.texto;
    L.marker(map.containerPointToLatLng([r.x, r.y]), {interactive: false, keyboard: false,
      icon: L.divIcon({className: '', iconSize: [0, 0], html: d})}).addTo(st.grupo);
  }
}

function cgDesenharRuasImagem(map, id, ctx) {
  const st = window.cgRuas[id];
  if (!st || !st.ativo || map.getZoom() < CG_ZOOM_MIN_RUAS) return false;
  ctx.save();
  ctx.font = CG_FONTE_RUA;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.lineJoin = 'round';
  for (const r of cgCalcularRotulosRuas(map, st.vias)) {
    ctx.save();
    ctx.translate(r.x, r.y);
    ctx.rotate(r.ang);
    ctx.lineWidth = 3.5; ctx.strokeStyle = '#000'; ctx.strokeText(r.texto, 0, 0);
    ctx.fillStyle = '#fff'; ctx.fillText(r.texto, 0, 0);
    ctx.restore();
  }
  ctx.restore();
  return true;
}

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

    // camadas de tiles na ordem de exibição (zIndex): Esri, ortofoto SC, rótulos Esri
    const camadasTile = [...el.querySelectorAll('.leaflet-tile-pane > .leaflet-layer')]
      .map((c, i) => [parseInt(c.style.zIndex || '0', 10), i, c])
      .sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    for (const [, , c] of camadasTile) {
      for (const img of c.querySelectorAll('img.leaflet-tile-loaded')) {
        const r = img.getBoundingClientRect();
        ctx.drawImage(img, r.left - r0.left, r.top - r0.top, r.width, r.height);
      }
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
    const ruasOsm = cgDesenharRuasImagem(map, id, ctx);
    cgDesenharNorte(ctx, 12, 12);
    cgDesenharEscala(map, ctx, r0.width, r0.height);
    const fundo = window.cgFundos[id];
    const scAtivo = !!fundo && fundo.modo === 'sc' && map.hasLayer(fundo.sc);
    const soSC = scAtivo && L.latLngBounds(CG_SC_CAIXA).contains(map.getBounds());
    const esri = 'Esri, Maxar, Earthstar Geographics';
    const credito = [
      soSC ? 'Ortofotos © SDE/SC (2012)'
           : scAtivo ? `Ortofotos © SDE/SC (2012) e imagens © ${esri}` : `Imagens © ${esri}`,
      map.hasLayer(window.cgRotulos[id] || L.layerGroup()) ? 'Rótulos © Esri' : '',
      ruasOsm ? 'Ruas © colaboradores do OpenStreetMap' : '',
    ].filter(Boolean).join(' · ');
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
            "crossOrigin": "anonymous", "zIndex": 1})   # crossOrigin: para exportar a imagem
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

    async def fundo(self, modo: str) -> None:
        """modo: 'esri' (padrão) ou 'sc' (ortofoto SC 2012, só cobre Santa Catarina)."""
        await self.leaflet.initialized()
        self._js(f"cgFundo({self.leaflet.id}, {json.dumps(modo)})")

    async def rotulos(self, modo: str) -> None:
        """modo: 'nenhum', 'esri' ou 'osm' (só nomes de ruas, do OpenStreetMap)."""
        await self.leaflet.initialized()
        self._js(f"cgRotulosModo({self.leaflet.id}, {json.dumps(modo)})")

    async def exportar_imagem(self, formato: str, nome: str) -> str:
        """Baixa a vista atual como PNG/JPG. Retorna 'ok' ou a mensagem de erro do navegador."""
        await self.leaflet.initialized()
        return await self._js(
            f"cgExportar({self.leaflet.id}, {json.dumps(formato)}, {json.dumps(nome)})",
            timeout=60)
