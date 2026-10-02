"""Rotas do main.py: /health e redirecionamento do endereço antigo do Render."""
import pytest
from fastapi.testclient import TestClient

import main

cliente = TestClient(main.app)


@pytest.mark.parametrize('caminho', ['/', '/?a=1&b=2'])
def test_onrender_redireciona_para_dominio(caminho):
    r = cliente.get(caminho, headers={'host': 'conversorgeo.onrender.com'}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers['location'] == f'https://{main.DOMINIO}{caminho}'


@pytest.mark.parametrize('host', ['conversorgeo.onrender.com', 'conversorgeo.com.br', 'localhost:8090'])
def test_health_responde_em_qualquer_endereco(host):
    r = cliente.get('/health', headers={'host': host}, follow_redirects=False)
    assert r.status_code == 200
    assert r.json() == {'status': 'ok'}


# ------------------------------------------------------------------ buscadores e AdSense
from ui import anuncios  # noqa: E402

CLIENTE = 'ca-pub-1234567890123456'


def test_robots_e_sitemap():
    r = cliente.get('/robots.txt', headers={'host': 'conversorgeo.com.br'})
    assert r.status_code == 200 and 'Sitemap: https://conversorgeo.com.br/sitemap.xml' in r.text
    r = cliente.get('/sitemap.xml', headers={'host': 'conversorgeo.com.br'})
    assert r.status_code == 200 and r.headers['content-type'].startswith('application/xml')
    for caminho in ('/', '/como-usar', '/sobre', '/privacidade', '/contato'):
        assert f'<loc>https://conversorgeo.com.br{caminho}</loc>' in r.text


def test_adsense_desligado_por_padrao(monkeypatch):
    monkeypatch.delenv('ADSENSE_CLIENT', raising=False)
    assert not anuncios.ativo() and anuncios.html_cabecalho() == ''
    assert cliente.get('/ads.txt', headers={'host': 'conversorgeo.com.br'}).status_code == 404


@pytest.mark.parametrize('valor', ['', 'pub-1234567890123456', 'ca-pub-12x', 'ca-pub-1"><script>'])
def test_adsense_ignora_codigo_invalido(monkeypatch, valor):
    monkeypatch.setenv('ADSENSE_CLIENT', valor)
    assert not anuncios.ativo()


def test_adsense_ligado(monkeypatch):
    monkeypatch.setenv('ADSENSE_CLIENT', CLIENTE)
    r = cliente.get('/ads.txt', headers={'host': 'conversorgeo.com.br'})
    assert r.status_code == 200
    assert r.text == 'google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n'
    assert f'adsbygoogle.js?client={CLIENTE}' in anuncios.html_cabecalho()

