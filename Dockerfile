# ==============================================================================
# Conversor Geo — imagem para o Render (plano Free)
# ==============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# --- Etapa 5: ODA File Converter (DWG <-> DXF) ---
# Baixar o .deb Linux x64 em https://www.opendesign.com/guestfiles/oda_file_converter
# (conferir a licença), informar a URL em ODA_DEB_URL e descomentar o bloco abaixo.
# ARG ODA_DEB_URL=""
# RUN apt-get update && apt-get install -y --no-install-recommends wget xvfb \
#     && wget -q "$ODA_DEB_URL" -O /tmp/oda.deb \
#     && apt-get install -y /tmp/oda.deb && rm /tmp/oda.deb \
#     && rm -rf /var/lib/apt/lists/*
# ENV QT_QPA_PLATFORM=offscreen

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080
CMD ["python", "main.py"]
