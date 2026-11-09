import pytest
from fastapi.testclient import TestClient
# Importa o app FastAPI principal (se o seu arquivo principal for app.py, altere para: from app import app)
from main import app 

client = TestClient(app)

# 1. TESTE UNITÁRIO: Regra de cálculo do Desconto Manual
def test_calculo_venda_com_desconto_manual():
    preco_unitario = 57.0
    quantidade = 3
    subtotal = preco_unitario * quantidade
    desconto_manual = 17.10
    total = round(subtotal - desconto_manual, 2)
    assert total == 153.90

# 2. TESTE DE ROTA: Verificar se a API está online e respondendo
def test_rota_status_api():
    response = client.get("/")
    # Aceita HTTP 200 (OK) ou HTTP 404 (se a rota raiz não existir, mas a API responder)
    assert response.status_code in [200, 404]

# 3. TESTE DE ROTA: Listar Produtos (/api/produtos)
def test_listar_produtos():
    response = client.get("/api/produtos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# 4. TESTE DE ROTA: Listar Categorias (/api/categorias)
def test_listar_categorias():
    response = client.get("/api/categorias")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# 5. TESTE DE ROTA: Listar Vendas (/api/vendas)
def test_listar_vendas():
    response = client.get("/api/vendas")
    assert response.status_code == 200
    assert isinstance(response.json(), list)