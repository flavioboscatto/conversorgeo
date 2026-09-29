# PLANO_CONVERSOR.md — Plano de implantação

Status: [ ] pendente · [~] em andamento · [x] concluída

**Ordem de trabalho (decidida em 2026-09-28):** desenvolver e testar localmente no navegador
(`.venv\Scripts\python.exe main.py`) antes de publicar no Render. A interface cresce a cada
etapa: cada etapa entrega também a sua parte visível na tela; a Etapa 6 vira acabamento.

**Situação em 2026-09-28:** Etapas 1 a 4 implementadas com testes automáticos (148 ok,
incluindo DXF → KML → DXF e DXF → SHP → DXF com resíduo < 1 mm). Interface com upload,
botão “Mostrar arquivo na imagem” (Esri World Imagery), painel de layers e “Converter e
baixar”. Pendentes: testes manuais (Google Earth, QGIS, arquivos reais do curso), Etapa 5
(DWG — fora por decisão: 4 entradas e 3 saídas), deploy no Render e Etapa 7.

---

## [~] Etapa 0 — Base do projeto e deploy de fumaça
**Situação:** motor movido e testado (65 testes ok), app local respondendo `/health`,
código no GitHub. Deploy no Render feito em 2026-09-28: https://conversorgeo.onrender.com
(`/health` ok; upload, SIGEF → KML e exportação de imagem testados no ar). UptimeRobot
configurado em `/health` a cada 5 min. Em 2026-09-29: domínio próprio
**https://conversorgeo.com.br** (Registro.br, modo avançado: `A` raiz → 216.24.57.1,
`www` → CNAME, redireciona para a raiz; certificados emitidos pelo Render; o endereço
`onrender.com` continua valendo). Pendente: teste manual de 20 min sem hibernar.
**Objetivo:** repositório estruturado, motor geodésico como módulo testado e app mínimo
publicado no Render (valida Docker e health check logo no início).

**Arquivos:** `CLAUDE.md`, `PLANO_CONVERSOR.md`, `requirements.txt`, `requirements-dev.txt`,
`Dockerfile`, `render.yaml`, `main.py`, `core/geodesia/motor_geodesico.py`,
`tests/test_motor_geodesico.py`.

**Tarefas:**
- Copiar `motos_geodesico.py` para `core/geodesia/motor_geodesico.py` acrescentando apenas `import math`.
- Testes do motor contra `pyproj` (EPSG 4674 ↔ 31982 e mais um fuso, ex. 31983):
  ida geo→UTM, volta UTM→geo e ida-e-volta.
- Teste que confirma o nome dos EPSG UTM usados (31960+fuso S, 31954+fuso N).
- Testes do `sexagesimal_para_decimal` com os formatos da planilha SIGEF (`48 32 28,781 W`).
- Publicar no Render e configurar o UptimeRobot em `/health`.

**Aceite:** diferença motor × pyproj < 1 mm em E/N e < 0,00001" em lat/lon;
app no ar respondendo `{"status": "ok"}` em `/health`.

**Verificar (sem alterar a fórmula):** o 4º retorno de `utm_para_lat_lon`
(convergência meridiana) é uma aproximação — comparar com pyproj e registrar a diferença.

**Teste manual:** abrir a URL do Render; aguardar 20 min sem uso e confirmar que o app não hibernou.

---

## [ ] Etapa 1 — Modelo interno e sistemas de referência
**Objetivo:** estrutura única de feições e conversão de qualquer entrada para SIRGAS 2000 geográfico.

**Arquivos:** `core/modelo.py`, `core/crs.py`, `tests/test_crs.py`,
`ui/pagina_principal.py`, `ui/formatos.py`.

**Na tela:** conversor de um ponto (geográfico decimal/GMS ↔ UTM), fuso/hemisfério só
quando UTM, sugestão de fuso pela longitude e aviso de fuso.

**Conteúdo:**
- `Estilo` (cor RGB, espessura, tipo de linha), `Feicao` (tipo ponto/linha/polígono/texto,
  coordenadas float64 com Z opcional, layer, estilo, texto, atributos), `Projeto` (feições + layers + CRS de origem).
- `SistemaRef`: geográfico (decimal ou GMS) ou UTM (fuso 17–25 S; 17–24 N — 25N não existe no EPSG).
- Aviso quando pontos caem a mais de 3° do meridiano central do fuso informado.
- Sugestão de fuso pela longitude.

**Aceite:** ida-e-volta UTM → geo → UTM < 1 mm; aviso de fuso disparado em caso de teste.

---

## [ ] Etapa 2 — Leitores DXF e SIGEF
**Objetivo:** reconhecer pontos, linhas, polígonos e textos.

**Arquivos:** `core/leitores/dxf.py`, `core/leitores/sigef.py`, testes e dados de exemplo.

**Regras DXF:** POINT/INSERT → ponto (nome do bloco em atributo); LINE, polyline aberta,
ARC, SPLINE → linha; polyline fechada, CIRCLE, HATCH → polígono; bulges e arcos discretizados;
cores ByLayer/ByBlock resolvidas (ACI e true color); TEXT/MTEXT associado ao ponto mais próximo
dentro da tolerância, senão texto solto.

**Regras SIGEF:** ler só as abas `perimetro_N` (a aba `identificacao` não é lida — sem
nome/CPF); coordenadas GMS ou UTM
conforme "Tipo de Coordenada"; gerar vértices (com sigmas, h, método, tipo de limite),
segmentos (limite + confrontante/CNS/matrícula) e polígono da parcela.

**Aceite:** contagens corretas no DXF de teste; `SIGEF.ods` de exemplo gera os vértices
FBSC-M/P/V com coordenadas iguais às da planilha.

---

## [ ] Etapa 3 — Escritores KML/KMZ e Shapefile
**Arquivos:** `core/escritores/kml.py`, `core/escritores/shp.py`, `assets/circulo.png`.

**KML/KMZ:** pasta por layer; cor ACI/RGB → `aabbggrr`; espessura mantida; ícone círculo
embutido no KMZ e colorido por IconStyle; texto atrelado a ponto = rótulo sem ícone
(IconStyle scale 0); texto solto = placemark só com rótulo.
**Limitação conhecida:** tracejados não existem no KML.

**SHP:** `_pontos`, `_linhas`, `_poligonos` (com Z quando houver); campos `LAYER`, `COR`,
`TEXTO` + atributos SIGEF (nomes ≤ 10 caracteres); `.prj` do EPSG escolhido; `.cpg` UTF-8; ZIP.

**Aceite:** abrir no Google Earth e no QGIS com cores, layers, ícones e textos corretos.

---

## [ ] Etapa 4 — Leitores KML/SHP e escritor DXF
**Arquivos:** `core/leitores/kml.py`, `core/leitores/shp.py`, `core/escritores/dxf.py`.

- KML/KMZ: pastas → layers; estilos → true color; Placemark só com nome → TEXT.
- SHP: ler `.prj` (se ausente, pedir o sistema ao usuário); campo de layer, se existir.
- DXF de saída: layers com cor, textos, Z; UTM ou geográfico (graus decimais).

**Aceite:** DXF → KML → DXF preserva coordenadas (resíduo < 1 mm após reprojeção), layers e cores.

---

## [ ] Etapa 5 — DWG via ODA File Converter
**Arquivos:** `core/leitores/dwg.py`, `core/escritores/dwg.py`, `Dockerfile`.

- Instalar ODA File Converter (Linux x64) no container; usar `ezdxf.addons.odafc`.
- Testar execução headless (`QT_QPA_PLATFORM=offscreen` ou `xvfb-run`).
- Conferir os termos de licença da ODA para uso em servidor público.

**Aceite:** um DWG real do curso converte nos dois sentidos; tempo e memória dentro do Render Free.

---

## [ ] Etapa 6 — Interface NiceGUI
**Arquivos:** `ui/pagina_principal.py`, `ui/mapa.py`, `ui/formularios.py`, `main.py`.

- Upload; escolha do sistema de entrada (fuso/hemisfério só quando UTM).
- Mapa com fundo de satélite, painel de layers (ligar/desligar) e resumo de feições.
- Escolha da saída; UTM desabilitado para KML; download do arquivo/ZIP.
- Mensagens de erro em linguagem de agrimensor; nada gravado em disco.

**Aceite:** fluxo completo com os quatro tipos de entrada, sem traceback na tela.

---

## [~] Etapa 7 — Documentação e publicação final
**Situação (2026-09-28):** `README.md` e manual do aluno (`docs/Manual_Conversor_Geo.docx`,
gerado por `docs/gerar_manual.py`) prontos; faltam as capturas de tela (marcadores [FIGURA N])
e a revisão do professor. Decisão: o app **não** se destina a arquivos grandes — a conferência
de memória/tempo com arquivos grandes foi retirada da etapa; vale o limite de upload da tela.

- README (uso, limitações, formatos), manual para alunos, revisão do `CLAUDE.md`.
- Conferir uso de memória e tempo de conversão com arquivos grandes no Render.

**Aceite:** aluno consegue converter um arquivo seguindo só o manual.
