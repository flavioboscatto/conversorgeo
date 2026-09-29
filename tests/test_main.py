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
