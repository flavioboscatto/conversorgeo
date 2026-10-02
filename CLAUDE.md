# CLAUDE.md — Conversor Geo (DXF/DWG ↔ KML ↔ Shapefile + SIGEF)

## Objetivo
App web para converter arquivos entre DXF/DWG, KML/KMZ e Shapefile, com a planilha
SIGEF/INCRA (.ods) como quarta entrada (somente leitura). Visualização sobre imagem
de satélite. Público: profissionais e alunos do Curso Técnico em Agrimensura (IFSC).

## Stack
- Python 3.12, interface **NiceGUI** (mapa Leaflet nativo).
- Núcleo: `ezdxf`, `pyshp`, `shapely`, `lxml`, `python-calamine`, `numpy`.
- Testes: `pytest` + `pyproj` (só como referência de conferência, não em produção).
- Deploy: **Render (plano Free)** via Docker; health check em `/health`.
- Desenvolvimento no Windows, versionamento no GitHub, edição com Claude Code.

## Arquitetura
```
conversor-geo/
├── main.py                     # entrada NiceGUI + rota /health
├── core/                       # NÃO importa nada de ui/
│   ├── modelo.py               # Feicao, Estilo, Camada, Projeto (modelo interno único)
│   ├── crs.py                  # SistemaRef + conversões usando o MotorGeodesico
│   ├── geodesia/motor_geodesico.py
│   ├── leitores/   dxf.py  kml.py  shp.py  sigef.py  dwg.py
│   └── escritores/ dxf.py  kml.py  shp.py  dwg.py
├── ui/                         # página, mapa, formulários
├── assets/circulo.png          # ícone de ponto do KMZ (branco, colorido via IconStyle)
└── tests/  (dados/ com arquivos de exemplo)
```
Fluxo: leitor → modelo interno (SIRGAS 2000 geográfico, float64) → visualização / escritor.

## Decisões fechadas
- Interface NiceGUI; hospedagem Render Free com UptimeRobot chamando `/health` a cada
  5 min. Só este serviço pode ficar acordado 24 h (cota de 750 h/mês da conta).
- Endereço público: **https://conversorgeo.com.br** (DNS no Registro.br; `www` redireciona
  para a raiz). `conversorgeo.onrender.com` continua ativo (não desligar no Render), mas o
  `main.py` redireciona com 301 para o domínio próprio; só `/health` responde nele.
- Site (Etapa 9): páginas `/`, `/como-usar`, `/sobre`, `/privacidade`, `/contato` com o mesmo
  cabeçalho/menu e rodapé (`ui/layout.py`; cabeçalho não fixo por causa do celular); textos
  em `ui/paginas_info.py` (Markdown). `/robots.txt` e `/sitemap.xml` no `main.py`.
  Contato: **conversorgeo@gmail.com**. Divulgação particular: o site **não cita o IFSC**.
- AdSense (`ui/anuncios.py`) só liga com a variável `ADSENSE_CLIENT=ca-pub-…` no Render
  (publica `/ads.txt` e o script); blocos com `ADSENSE_SLOT_FAIXA`, `_LATERAL`, `_CONTEUDO`.
  A Privacidade troca o texto de publicidade sozinha conforme a variável. Sem anúncio sobre o mapa.
- Build Filters do Render ignoram `docs/**`, `tests/**`, `README.md`, `CLAUDE.md` e
  `PLANO_CONVERSOR.md` (commits só de documentação não geram deploy).
- Entradas: DXF, DWG, KML/KMZ, SHP (.zip), SIGEF (.ods). Saídas: DXF, DWG, KML/KMZ, SHP.
- SIRGAS 2000 é o datum padrão; KML entra e sai em WGS84 geográfico.
- UTM exige fuso e hemisfério informados pelo usuário (entrada e saída).
  **UTM nunca é saída para KML.**
- DXF/DWG → KML: manter layers (uma pasta por layer), cores e espessuras; ponto com
  ícone de círculo (não o padrão); texto atrelado a ponto vira rótulo, sem ícone.
- DXF/DWG → SHP: três shapes (pontos, linhas, polígonos) com campo `LAYER`,
  `.prj` e `.cpg` (UTF-8), entregues em ZIP.
- DXF é o formato nativo; DWG entra/sai via ODA File Converter (Etapa 5).
- SIGEF: só as abas `perimetro_N` são lidas (geometria); a aba `identificacao`
  (nome, CPF etc.) **não é lida**. Nada gravado em disco.
- `tests/dados/SIGEF.ods` fica fora do git (pode conter dados reais); versionar só
  uma cópia anonimizada.

## Padrões provisórios (a confirmar com o usuário)
- Tolerância texto↔ponto: 0,5 m. Arcos/círculos discretizados a cada 1°.
- SIGEF gera layers por tipo de vértice (M, P, V); segmentos levam tipo de limite e confrontante.
- Fuso sugerido automaticamente a partir da longitude (entrada KML).
- Fundo do mapa: Esri World Imagery; Google Satélite só com chave da Maps Platform.

## Regras de trabalho
1. Somente diffs / trechos alterados, indicando arquivo, classe e método.
2. Sem refatoração fora do escopo; sugestões em lista separada.
3. Uma etapa do `PLANO_CONVERSOR.md` por vez, com confirmação antes de avançar.
4. Se o plano conflitar com o código real, parar e perguntar.
5. **Nunca alterar a matemática do `MotorGeodesico`** nem códigos EPSG sem confirmação explícita.
6. Após cada lote: `python -m py_compile` nos arquivos alterados e `pytest`.
7. Atualizar este arquivo e o plano ao concluir cada etapa.

## Convenções
- Coordenadas sempre em float64; nunca float32.
- Interface e mensagens em português do Brasil, vírgula decimal na tela.
- Na tela, escrever **coordenadas geodésicas** (nunca "geográficas"). No código os nomes
  `geografico`/`GEO` continuam.
- Tema da interface: verde claro (`#66BB6A`).
- Tela: **formato primeiro** (ex.: Entrada DXF → Saída KML), depois o sistema de coordenadas.
  KML (entrada e saída) trava o sistema em geodésicas; SIGEF usa o sistema da planilha;
  SHP usa o .prj (o sistema escolhido só vale sem .prj).
- 5 entradas (DXF, KML/KMZ, SHP, SIGEF, TXT/CSV) e 3 saídas (DXF, KML/KMZ, SHP).
  **DWG fora de vez** (decisão de 2026-10-02): salvar como DXF no CAD.
- TXT/CSV (`core/leitores/txt.py`, Etapa 8): usuário aponta as colunas (nome, E/lon, N/lat,
  h, código) num painel que aparece após o upload; separador e cabeçalho detectados e
  corrigíveis. Sistemas: UTM, geodésicas decimais ou **gg,mmss** (opção extra só para TXT;
  `SistemaRef.gms=True`); sul/oeste com sinal negativo. Código → layer (cor da `PALETA`).
  Geometria: só pontos, ou pontos + linha/polígono na ordem do arquivo — **todos os pontos**
  (padrão; layer `LIGACAO`) ou **por código** (uma por layer; só aparece com coluna de código).
  Erros apontam o número da linha do arquivo.
- gg,mmss é convertido por `ggmmss_para_decimal` (lê o texto, completa com zeros à direita).
  **Não usar** `MotorGeodesico.sexagesimal_para_decimal` para valores compactos de 1 bloco:
  ele completa com zeros à esquerda (`zfill`) e só acerta com exatamente 8 dígitos após a
  vírgula (`-27,3543092` viraria 27°03'54"). Motor não alterado (regra 5); o formato com
  espaços da planilha SIGEF (`27 35 43,092 S`) segue correto.
- Fluxo: upload → **“Mostrar arquivo na imagem”** (lê e desenha sobre Esri World Imagery)
  → “Converter e baixar”. Sem ponto digitado na entrada.
- **Editar importação** (✎ na lista): o item guarda o arquivo original, o sistema da tela e as
  escolhas do TXT; editar volta tudo para a entrada e “Atualizar na imagem” substitui o item
  no mesmo lugar (mesmo id/prefixo). Arquivo novo durante a edição vira importação nova.
- Múltiplas importações: cada arquivo com seu formato/sistema; saída **sempre um arquivo
  único** (`juntar`); layer repetida ganha o nome do arquivo na frente.
- Cor ACI 7 (branca no fundo preto do AutoCAD) entra como **preto**; no DXF de saída,
  preto/branco são gravados como ACI 7. Cor trocada no painel de layers vale para mapa,
  imagem e arquivos de saída (`recolorir`).
- Imagem (croqui): vista atual do mapa em PNG/JPG, gerada no navegador — fundo Esri,
  rótulos Esri opcionais e só as layers habilitadas; crédito da Esri sempre impresso.
- Fundo do mapa: **Esri World Imagery (padrão)** ou **Ortofoto SC 2012** (WMS aberto do
  SIGSC, camada `OrtoRGB-Landsat-2012`, 0,39 m, só SC; PNG transparente por cima da Esri).
  Bing descartado (serviço em encerramento); Google/Mapbox/MapTiler exigem chave.
- Rótulos: nenhum / Esri (números de endereço a partir do zoom 18) / **OpenStreetMap** (só
  nomes de ruas, via Overpass API no navegador, zoom ≥ 15, 3 tentativas — o serviço oscila).
- Web Mercator (EPSG:3857) **não** é suportado por decisão: o usuário reprojeta antes.
- `core/conversor.py` é a porta de entrada do núcleo (`ler`/`escrever`); ícone do KMZ é
  gerado em código (`png_circulo`), sem arquivo em `assets/`.
- Desenvolvimento local: `$env:DEV='1'; $env:PORT='8090'; .venv\Scripts\python.exe main.py`
  (recarrega sozinho). DXF de teste: `python -m tests.exemplo_dxf` → `tests/dados/exemplo_utm22s.dxf`.
- Erros explicados em linguagem de agrimensor, sem traceback para o usuário.
- `core/` independente da interface (permite trocar NiceGUI por FastAPI no futuro).
- Limite de RAM do Render Free: 512 MB — evitar cópias desnecessárias de geometrias grandes.
  O app **não se destina a arquivos grandes** (decisão do usuário); vale o limite de upload
  da tela (`TAMANHO_MAX_MB` em `ui/pagina_principal.py`).
- EPSG SIRGAS 2000: 4674 (geográfico); UTM Sul = 31960 + fuso (ex.: 31982 = 22S);
  UTM Norte = 31954 + fuso (ex.: 31976 = 22N) **só para fusos 17N–22N**; 23N = 6210 e
  24N = 6211 (31954+23 = 31977 é o 17S!). Conferido por teste na Etapa 0.

## Observações técnicas
- A planilha ODS do INCRA **não abre com pandas/odfpy** (atributo booleano fora do padrão).
  Usar `python-calamine` ou leitura direta do `content.xml`.
- `motor_geodesico.py` original vinha sem `import math`; foi a única alteração permitida.
