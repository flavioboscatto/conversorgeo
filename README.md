# Conversor Geo

Aplicativo web para converter levantamentos entre **DXF**, **KML/KMZ** e **Shapefile**, com a
**planilha do SIGEF/INCRA (.ods)** e **TXT/CSV de pontos** como entradas, conferência sobre imagem de satélite ou
ortofoto e exportação de **croqui de localização** (PNG/JPG).
Feito para o Curso Técnico em Agrimensura do IFSC.

**No ar:** https://conversorgeo.com.br
**Manual do aluno:** [`docs/Manual_Conversor_Geo.docx`](docs/Manual_Conversor_Geo.docx)

## Formatos

| Formato | Entrada | Saída | Sistema |
|---|---|---|---|
| DXF | sim | sim | geodésicas ou UTM (informado pelo usuário) |
| KML / KMZ | sim | sim | sempre geodésicas (WGS 84 ≡ SIRGAS 2000 para fins práticos) |
| Shapefile (.zip) | sim | sim | lido do `.prj`; saída com `.prj` e `.cpg` UTF-8 |
| Planilha SIGEF (.ods) | sim | — | lido da planilha; só as abas `perimetro_N` (a aba de identificação não é lida) |
| TXT / CSV (pontos) | sim | — | UTM, geodésicas decimais ou geodésicas gg,mmss (sul e oeste negativos) |

No TXT/CSV o usuário aponta as colunas (nome, E/longitude, N/latitude, h, código); o
separador (`;`, tabulação, vírgula ou espaço) e o cabeçalho são detectados e podem ser
corrigidos. Cada código vira uma layer; opcionalmente os pontos são ligados na ordem do
arquivo, formando linha ou polígono — todos juntos (layer `LIGACAO`) ou um por código. Exemplo de gg,mmss: `-27,3543092` =
27°35'43,092" S.

Datum: SIRGAS 2000. UTM Sul 17–25 (EPSG 31977–31985), UTM Norte 17–24
(31971–31976, 6210, 6211). Vários arquivos, cada um com seu sistema, podem ser somados numa
**saída única**.

## Como usar

1. Entrada: escolher formato e sistema, enviar o arquivo e clicar em **Mostrar arquivo na imagem**.
2. Conferir no mapa (layers, cores, atributos, avisos). Para corrigir sistema, colunas ou
   geometria, usar o ✎ (**Editar importação**) do arquivo na lista. Repetir para outros
   arquivos, se for o caso.
3. Saída: escolher formato e sistema e clicar em **Converter e baixar**.
4. Croqui: escolher fundo (Esri ou Ortofoto SC 2012) e rótulos (Esri ou OpenStreetMap),
   enquadrar e clicar em **Exportar imagem**.

Os arquivos ficam só na memória da sessão; nada é gravado no servidor.

## Limitações conhecidas

- DWG não é aceito: salvar como DXF no CAD.
- TXT/CSV: só pontos (com ou sem linha/polígono ligando-os); arquivos de equipamento com
  formato próprio precisam ser exportados como texto com colunas.
- Web Mercator (EPSG:3857) e outros sistemas não são aceitos: reprojetar no QGIS antes.
- Tracejados não existem no KML; arcos e círculos viram segmentos de 1°; furos de polígonos
  não são convertidos.
- Cor 7 do AutoCAD (branca no fundo preto) sai preta nas saídas.
- Rótulos Esri mostram números de endereço a partir do zoom 18; rótulos do OpenStreetMap
  dependem do serviço público Overpass, que às vezes demora ou fica indisponível.
- Ortofoto SC: aerolevantamento 2010–2012, só Santa Catarina.

## Desenvolvimento

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests -q
```

Servidor local com recarga automática (PowerShell):

```bash
$env:DEV='1'; $env:PORT='8090'; .venv\Scripts\python.exe main.py
```

- `core/` — núcleo sem interface: modelo, sistemas de referência, motor geodésico, leitores
  e escritores (`core/conversor.py` é a porta de entrada).
- `ui/` — página NiceGUI e mapa Leaflet.
- `tests/` — testes (conferência contra `pyproj`); `python -m tests.exemplo_dxf` gera o DXF
  de exemplo em `tests/dados/`.
- `docs/gerar_manual.py` — gera o manual (requer `python-docx`, fora das dependências do app).

Páginas do site: conversor (`/`), `/como-usar`, `/sobre`, `/privacidade` e `/contato`
(`ui/paginas_info.py`), além de `/robots.txt` e `/sitemap.xml`. Anúncios do Google AdSense
ficam desligados até definir `ADSENSE_CLIENT` no Render (ver `ui/anuncios.py`).

Deploy: Render (plano Free, Docker, health check em `/health`), domínio próprio
`conversorgeo.com.br` (DNS no Registro.br; `www` redireciona para a raiz), mantido acordado
por monitor externo. Regras de trabalho e decisões do projeto em [`CLAUDE.md`](CLAUDE.md);
etapas em [`PLANO_CONVERSOR.md`](PLANO_CONVERSOR.md).
