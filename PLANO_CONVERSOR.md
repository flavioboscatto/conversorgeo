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

## [x] Etapa 5 — DWG só na entrada, via GNU LibreDWG
**Histórico:** o plano original (ODA File Converter, entrada e saída) foi descartado em
2026-10-02 — o uso comercial (site com anúncios) exige assinatura paga da ODA. Reaberta em
2026-10-07 com o **LibreDWG** (GPLv3, `dwg2dxf` chamado como programa separado), **só entrada**:
o LibreDWG não grava DWG nos formatos atuais.

**Arquivos:** `core/leitores/dwg.py`, `tests/test_dwg.py`, `tests/dados/exemplo_utm22s.dwg`
(gerado do DXF de exemplo, formato 2000), `Dockerfile` (etapa que compila o `dwg2dxf` 0.14,
fonte conferida por SHA-256), `ferramentas/libredwg/` (exe + DLLs para o Windows, fora do git).

- DWG R13 a 2018 (AC1012–AC1032); o mais novo que o LibreDWG lê é o 2018.
- Conversão em processo separado: 60 s, 256 MB, pasta temporária em RAM (`/dev/shm`),
  DXF gerado até 80 MB. IMAGE e nuvem de pontos ignoradas; objetos do Civil 3D não vêm.
- DWG até 2004: o LibreDWG grava texto UTF-8 num DXF que se declara em codepage →
  `corrigir_texto` regrava com escapes `\U+XXXX` (senão “Área” vira “Ã\x81rea”).
- Coordenadas locais não são aceitas (decisão do usuário: exigiria ajuste manual).
- O teste achou bug no leitor DXF (entidade sem layer, ex. SECTIONOBJECT) — corrigido.

**Teste (2026-10-07):** planialtimétrico real AC1032 (UTM 22S) do usuário: 0,3 s, 40 pontos,
91 linhas, 21 polígonos, 105 textos, 11 layers, acentos e atributos de bloco corretos.
**No ar (2026-10-07):** o 1º build falhou por falta de `pkg-config` no `configure`; corrigido
(685daf8, passos separados e `make -j2`). Build concluído e DWG testado pelo usuário no site.

**Aceite:** DWG real importa no ar (Render) com o mesmo resultado do teste local.

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

---

## [~] Etapa 8 — Entrada TXT/CSV com colunas escolhidas
**Situação (2026-10-02):** implementada e testada (`core/leitores/txt.py`, `tests/test_txt.py`,
painel de colunas em `ui/pagina_principal.py`; exemplos em `tests/dados/exemplo_txt_*`).
Conferida no navegador: UTM 22S (CSV `;` com cabeçalho) e gg,mmss (tabulação, sem cabeçalho)
caem no mesmo lugar. Testada pelo usuário e publicada (8f33b80). Manual do aluno v1.1 com a
seção 4.3, o exemplo 5.3, erros e exercícios de TXT/CSV (2026-10-02); falta a captura de tela
da FIGURA 3 (quadro Colunas do arquivo), junto das demais figuras.

- Extensões `.txt` e `.csv`; separador `;`, tabulação, vírgula ou espaço (detectado, corrigível);
  cabeçalho detectado; decimal com vírgula ou ponto.
- Colunas: E/Longitude e N/Latitude obrigatórias; nome, h/Z e código opcionais.
- Sistemas: UTM (fuso/hemisfério), geodésicas decimais, geodésicas gg,mmss; sul/oeste negativos.
- Código → layer. Geometria: só pontos / pontos + linha / pontos + polígono, na ordem do
  arquivo, ligando todos os pontos (padrão, layer LIGACAO) ou por código (uma por layer);
  grupo com poucos pontos gera aviso.

**Aceite:** arquivo de estação total/GNSS do curso importado só com o painel, sem editar o arquivo.

---

## [~] Etapa 9 — Conteúdo do site e AdSense (opção A)
Plano combinado em 2026-09-29; e-mail de contato **conversorgeo@gmail.com**. Usuário decidiu
não mexer no AdSense por enquanto.

**Situação (2026-10-02):** Fase 1 implementada (`ui/layout.py`, `ui/paginas_info.py`,
`ui/anuncios.py`, rotas no `main.py`, testes em `tests/test_main.py`) e conferida no navegador
(desktop e celular). AdSense desligado: sem `ADSENSE_CLIENT`, nenhum script, `/ads.txt` = 404 e
a Privacidade diz que o site não exibe anúncios. Pendente: nome do responsável
(`RESPONSAVEL` em `ui/paginas_info.py`), Fases 2 e 3.

- Fase 1 (sem cadastro): páginas `/como-usar`, `/sobre`, `/privacidade` (LGPD), `/contato`;
  links no cabeçalho e rodapé; `robots.txt` e `sitemap.xml`; ganchos do AdSense (`<head>`,
  `/ads.txt`, espaços de anúncio) ligados só pelas variáveis `ADSENSE_CLIENT`/`ADSENSE_SLOT_*`.
- Fase 2 (~1 mês depois): conta AdSense, variável no Render, pedido de análise, mensagem de
  consentimento do Google para visitantes da Europa.
- Fase 3 (após aprovação): blocos responsivos fora do mapa; conferir desktop/celular e croqui.
- Pode ser feito já, sem código: Google Search Console (registro TXT no Registro.br).
