# ==============================================================================
# Conversor Geo — imagem para o Render (plano Free)
# ==============================================================================

# --- Etapa 1: compila o dwg2dxf do GNU LibreDWG (GPLv3) para a entrada DWG ---
# Fica separada para o Docker reaproveitar quando só o código do app muda.
# Para trocar de versão: nova versão e SHA-256 do .tar.xz de https://ftp.gnu.org/gnu/libredwg/
FROM python:3.12-slim AS libredwg
ARG LIBREDWG_VERSAO=0.14
ARG LIBREDWG_SHA256=62ebb73b984f865960f20ed26619ea5f8789d5e3fd088fa40a2598384da81275
# passos separados: se algo falhar, o log do Render mostra qual
# (o configure do LibreDWG exige pkg-config, que não vem na imagem slim)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential pkg-config curl ca-certificates xz-utils
RUN curl -fsSL --retry 3 -o /tmp/libredwg.tar.xz \
       "https://ftp.gnu.org/gnu/libredwg/libredwg-${LIBREDWG_VERSAO}.tar.xz" \
    && echo "${LIBREDWG_SHA256}  /tmp/libredwg.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/libredwg.tar.xz -C /tmp
WORKDIR /tmp/libredwg-${LIBREDWG_VERSAO}
RUN ./configure --disable-shared --enable-static --disable-bindings --disable-python \
       --disable-docs --disable-werror
# -j2: arquivos C muito grandes; mais compilações em paralelo podem estourar a memória do build
RUN make -j2 -C src \
    && make -j2 -C programs dwg2dxf \
    && install -m 755 programs/dwg2dxf /usr/local/bin/dwg2dxf \
    && /usr/local/bin/dwg2dxf --version

# --- Etapa 2: o app ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=libredwg /usr/local/bin/dwg2dxf /usr/local/bin/dwg2dxf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "main.py"]
