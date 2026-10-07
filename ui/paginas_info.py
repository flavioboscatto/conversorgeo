# ==============================================================================
# Páginas de conteúdo: Como usar, Sobre, Privacidade e Contato.
# Textos em Markdown; mesmo cabeçalho/rodapé do conversor (ui/layout.py).
# ==============================================================================
from nicegui import ui

from ui import anuncios, layout

ATUALIZACAO = "2 de outubro de 2026"
# Nome exibido como responsável pelo site em “Sobre” e “Privacidade” (vazio = só o e-mail)
RESPONSAVEL = ""


def _pagina(caminho: str, descricao: str, texto: str) -> None:
    layout.preparar(descricao)
    layout.cabecalho(caminho)
    with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-4"):
        with ui.card().classes("w-full"):
            ui.markdown(texto).classes("w-full cg-texto")
        anuncios.espaco("CONTEUDO")
    layout.rodape()


def _responsavel() -> str:
    if RESPONSAVEL:
        return f"{RESPONSAVEL}, pelo e-mail [{layout.EMAIL_CONTATO}](mailto:{layout.EMAIL_CONTATO})"
    return f"o responsável pelo site, pelo e-mail [{layout.EMAIL_CONTATO}](mailto:{layout.EMAIL_CONTATO})"


# ------------------------------------------------------------------ Como usar
COMO_USAR = """
# Como usar o Conversor Geo

O Conversor Geo converte levantamentos entre **DXF**, **KML/KMZ** e **Shapefile**, lê
desenhos **DWG**, a **planilha do SIGEF/INCRA** e arquivos de pontos em **TXT/CSV**, mostra tudo sobre imagem de
satélite e exporta um **croqui de localização** em PNG ou JPG. Todo o processamento usa o
**SIRGAS 2000**.

## Formatos aceitos

| Formato | Entrada | Saída | Sistema de coordenadas |
|---|---|---|---|
| DXF | sim | sim | geodésicas ou UTM, informado por você |
| DWG (AutoCAD) | sim | — | geodésicas ou UTM, informado por você |
| KML / KMZ | sim | sim | sempre geodésicas (WGS 84) |
| Shapefile (.zip) | sim | sim | lido do `.prj`; a saída leva `.prj` e `.cpg` |
| Planilha SIGEF (.ods) | sim | — | lido da planilha (só as abas `perimetro_N`) |
| TXT / CSV (pontos) | sim | — | UTM, geodésicas decimais ou gg,mmss |

O DWG é aceito só na **entrada**, até o formato do AutoCAD 2018 (o usado pelas versões
recentes). Imagens e nuvens de pontos anexadas ao desenho são ignoradas, e objetos próprios do
Civil 3D (pontos COGO, superfícies) não são lidos. O desenho precisa estar em coordenadas
georreferenciadas (UTM ou geodésicas); desenhos em coordenadas locais não são aceitos.

## Passo a passo

1. **Entrada:** escolha o **formato** do arquivo e depois o **sistema de coordenadas**.
   Para UTM, informe o **fuso** e o **hemisfério** — o mesmo par E/N representa lugares
   diferentes em fusos diferentes.
2. Envie o arquivo (até 10 MB) e clique em **Mostrar arquivo na imagem**.
3. **Confira no mapa** se o desenho caiu no lugar certo. Esse é o principal controle de
   qualidade da conversão. No quadro **Layers** é possível ligar/desligar e trocar a cor de
   cada layer; a cor nova vale também para os arquivos de saída.
4. Errou alguma escolha? Clique no **✎ (Editar importação)** do arquivo na lista, corrija e
   clique em **Atualizar na imagem**.
5. Para juntar vários arquivos, repita os passos 1 e 2 — cada um com o seu formato e o seu
   sistema. A saída é **sempre um arquivo único** com tudo.
6. **Saída:** escolha o formato e o sistema e clique em **Converter e baixar**.

## Pontos em TXT ou CSV

Depois de enviar o arquivo, aparece o quadro **Colunas do arquivo**:

- o **separador** (ponto e vírgula, tabulação, vírgula ou espaço) e o **cabeçalho** são
  detectados automaticamente e podem ser corrigidos;
- aponte as colunas de **E / Longitude** e **N / Latitude** e, se houver, **nome do ponto**,
  **h / Z** e **código** — cada código vira uma layer;
- escolha **só pontos**, **pontos e linha** ou **pontos e polígono**. Os pontos são ligados
  na ordem do arquivo: todos juntos ou um traçado por código.

Nas coordenadas geodésicas, **sul e oeste levam sinal negativo**. No formato **gg,mmss**,
`-27,3543092` significa 27°35'43,092" S.

## Croqui de localização

No quadro **Imagem**, escolha o fundo (**Esri** ou **Ortofoto SC 2012**, só em Santa
Catarina) e os rótulos (**Esri** ou **OpenStreetMap**, só nomes de ruas), deixe ligadas só as
layers que devem aparecer, enquadre o mapa e clique em **Exportar imagem**. O croqui sai com
seta de norte, escala em barra e o crédito das fontes, que deve ser mantido.

## Mensagens mais comuns

| Mensagem | O que fazer |
|---|---|
| “As coordenadas parecem UTM…” | Escolher UTM, com fuso e hemisfério corretos. |
| “As coordenadas parecem geodésicas…” | Escolher Geodésicas. |
| “…nenhuma coordenada cabe em…” | O arquivo está em outro sistema (ex.: Web Mercator). Reprojetar no QGIS para SIRGAS 2000 e importar de novo. |
| “…a mais de 3° do meridiano central…” | O fuso informado não é o dos pontos: usar o fuso sugerido. |
| “…linha N…” (TXT/CSV) | Conferir separador, colunas e formato das coordenadas naquela linha do arquivo. |

## Cuidados

- Linhas brancas do AutoCAD (cor 7) saem **pretas** nas saídas; troque a cor no quadro
  Layers, se quiser outra.
- Tracejados não existem no KML; arcos e círculos viram segmentos de 1°; furos de polígonos
  não são convertidos.
- A imagem de fundo serve para **conferência visual e croqui**, não para medição.
"""

# ------------------------------------------------------------------ Sobre
SOBRE = """
# Sobre o Conversor Geo

O Conversor Geo é um aplicativo gratuito, feito para **profissionais e estudantes de
Agrimensura, Topografia e Geoprocessamento** que precisam levar um levantamento de um
programa para outro — do CAD para o Google Earth, do SIGEF para o QGIS, de uma planilha de
pontos para o CAD — sem perder layers, cores e atributos.

## O que ele faz

- Converte entre **DXF**, **KML/KMZ** e **Shapefile**, mantendo layers, cores, espessuras,
  rótulos e atributos, e lê desenhos **DWG** do AutoCAD.
- Lê a **planilha do SIGEF/INCRA** (vértices, limites e perímetro) e arquivos de pontos em
  **TXT/CSV** com as colunas que você indicar.
- Mostra tudo sobre **imagem de satélite** para conferência e exporta **croqui de
  localização** com norte e escala.
- Junta vários arquivos, cada um no seu sistema de coordenadas, numa **saída única**.

## Como as coordenadas são tratadas

Todo arquivo é levado a coordenadas geodésicas **SIRGAS 2000**, com precisão de 64 bits, e
convertido para o sistema de saída só na gravação. As conversões UTM usam um motor de
cálculo próprio, conferido por testes automáticos contra a biblioteca de referência PROJ
(diferenças menores que 1 mm). O fuso e o hemisfério UTM são sempre **informados por você**
— o aplicativo apenas sugere e avisa quando algo não confere.

## Limitações

- DWG só na entrada (até o formato AutoCAD 2018), sem objetos do Civil 3D.
- Não aceita desenhos em coordenadas locais nem arquivos em Web Mercator ou em outros datums.
- Não se destina a arquivos grandes: o limite é 10 MB por arquivo.
- A imagem de fundo é para conferência visual, não para medição.

## Responsável

{responsavel}

Encontrou um erro ou tem uma sugestão? Veja a página [Contato](/contato).
"""

# ------------------------------------------------------------------ Privacidade
PRIVACIDADE = """
# Política de privacidade

*Última atualização: {atualizacao}.*

Esta política explica quais dados o Conversor Geo (**{dominio}**) trata e por quê, conforme
a Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018 — LGPD). Dúvidas e pedidos
sobre seus dados: {responsavel}.

## Arquivos que você envia

- Os arquivos são **processados na memória** do servidor apenas para converter e mostrar no
  mapa. **Não são gravados em disco**, não são compartilhados e não são usados para nenhum
  outro fim.
- Eles ficam disponíveis enquanto a página estiver aberta (para permitir a edição da
  importação) e são **descartados** quando você remove o arquivo da lista, limpa a importação
  ou fecha a página.
- Na planilha do SIGEF, a aba de identificação (nome, CPF e outros dados do proprietário)
  **não é lida**.

## Cadastro e cookies

- O site **não tem cadastro nem login**.
- O Conversor Geo **não usa cookies próprios** de rastreamento ou de análise de audiência.

## Registros técnicos

Como qualquer site, o serviço de hospedagem e o próprio aplicativo podem manter **registros
técnicos de acesso** (por exemplo, endereço IP, data e hora e página acessada), usados
apenas para segurança, estabilidade e diagnóstico de falhas.

## Serviços de terceiros usados pelo mapa

Para desenhar o mapa, o seu navegador busca dados diretamente nestes serviços, que recebem o
seu endereço IP e a área do mapa visualizada — **nunca os seus arquivos**:

- **Esri** — imagem de satélite e rótulos de ruas e lugares;
- **SDE/SC (SIGSC)** — ortofoto de Santa Catarina 2012, quando escolhida;
- **OpenStreetMap (Overpass API)** — nomes de ruas, quando escolhidos.

{publicidade}

## Seus direitos

A LGPD garante, entre outros, os direitos de confirmação, acesso, correção e eliminação de
dados pessoais (art. 18). Como o Conversor Geo não guarda os seus arquivos nem mantém
cadastro, normalmente não há dados pessoais armazenados a seu respeito; ainda assim, você
pode fazer qualquer pedido pelo e-mail de contato.

## Alterações

Esta política pode ser atualizada; a data no início da página indica a versão em vigor.
"""

PUBLICIDADE_ATIVA = """
## Publicidade

O site exibe anúncios do **Google AdSense**. O Google e seus parceiros podem usar cookies
para mostrar anúncios com base em visitas anteriores a este e a outros sites. Saiba como o
Google usa esses dados em
[policies.google.com/technologies/partner-sites](https://policies.google.com/technologies/partner-sites)
e desative a personalização de anúncios em
[myadcenter.google.com](https://myadcenter.google.com).
"""

PUBLICIDADE_INATIVA = """
## Publicidade

No momento, o site **não exibe anúncios**. Se passar a exibir, esta política será
atualizada antes, informando o serviço usado e os cookies envolvidos.
"""

# ------------------------------------------------------------------ Contato
CONTATO = """
# Contato

Dúvidas, sugestões e relatos de erros: **[{email}](mailto:{email})**.

## Para relatar um erro

Ajuda muito enviar:

1. o **arquivo de entrada**, se puder ser compartilhado — **sem dados pessoais** (por
   exemplo, sem a aba de identificação da planilha do SIGEF);
2. o **formato e o sistema** escolhidos na entrada e na saída (fuso e hemisfério, se UTM);
3. a **mensagem** que apareceu ou o que saiu diferente do esperado;
4. no caso do croqui, o **fundo**, os **rótulos** e a escala (barra) do mapa.

Os e-mails são usados apenas para responder ao seu contato.
"""


def registrar() -> None:
    """Cria as rotas das páginas de conteúdo (chamar uma vez, no main.py)."""

    @ui.page("/como-usar", title="Como usar — Conversor Geo")
    def como_usar():
        _pagina("/como-usar", "Passo a passo para converter DXF, KML/KMZ, Shapefile, planilha "
                "SIGEF e TXT/CSV, conferir no mapa e exportar croqui de localização.", COMO_USAR)

    @ui.page("/sobre", title="Sobre — Conversor Geo")
    def sobre():
        email = f"[{layout.EMAIL_CONTATO}](mailto:{layout.EMAIL_CONTATO})"
        quem = f"Mantido por {RESPONSAVEL}. Contato: {email}" if RESPONSAVEL else f"Contato: {email}"
        _pagina("/sobre", "O que é o Conversor Geo, como trata as coordenadas (SIRGAS 2000, "
                "UTM) e suas limitações.", SOBRE.format(responsavel=quem))

    @ui.page("/privacidade", title="Política de privacidade — Conversor Geo")
    def privacidade():
        texto = PRIVACIDADE.format(
            atualizacao=ATUALIZACAO, dominio=layout.DOMINIO, responsavel=_responsavel(),
            publicidade=PUBLICIDADE_ATIVA if anuncios.ativo() else PUBLICIDADE_INATIVA)
        _pagina("/privacidade", "Como o Conversor Geo trata os arquivos enviados e os dados "
                "de acesso (LGPD).", texto)

    @ui.page("/contato", title="Contato — Conversor Geo")
    def contato():
        _pagina("/contato", "Fale com o Conversor Geo: dúvidas, sugestões e relatos de erros.",
                CONTATO.format(email=layout.EMAIL_CONTATO))
