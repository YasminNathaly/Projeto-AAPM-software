import os
from typing import Optional
from fastapi import FastAPI, Request, Depends, Form, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel

# 1. Importações do banco e dos modelos com Fallback de Segurança
from app.database import engine, Base, get_db

# 2. Importar o router de autenticação
from app.routers.auth_router import router as auth_router

# Tentativa segura de carregar cada modelo individualmente
try:
    from app.models.produto import Produto
except ImportError:
    Produto = None

try:
    from app.models.usuario import Usuario
except ImportError:
    Usuario = None

try:
    from app.models.categoria import Categoria
except ImportError:
    Categoria = None

try:
    from app.models.fornecedor import Fornecedor
except ImportError:
    Fornecedor = None

try:
    from app.models.venda import Venda
except ImportError:
    Venda = None


# 2. Cria as tabelas automaticamente no MySQL (apenas dos modelos existentes)
Base.metadata.create_all(bind=engine)

# 3. Inicializa o FastAPI
app = FastAPI(
    title="Sistema AAPM - Gestão de Estoque e Vendas",
    version="1.0.0"
)

# Contexto de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE CAMINHOS
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Aponta para a pasta app/templates
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

# Aponta para a pasta app/static
caminho_static_correto = os.path.join(BASE_DIR, "app", "static")
app.mount("/static", StaticFiles(directory=caminho_static_correto), name="static")

# ─────────────────────────────────────────────────────────────────────────────
# INCLUIR ROUTERS
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(auth_router)

# ─────────────────────────────────────────────────────────────────────────────
# HANDLERS DE EXCEÇÃO PERSONALIZADOS
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/admin"):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "status": "erro",
                "mensagem": f"O recurso ou endpoint '{request.url.path}' não foi encontrado no sistema."
            }
        )
    
    return templates.TemplateResponse(
        request=request,
        name="public/404.html",
        status_code=status.HTTP_404_NOT_FOUND
    )


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS PYDANTIC
# ─────────────────────────────────────────────────────────────────────────────

class ProdutoSchema(BaseModel):
    nome: str
    preco: float
    tamanho: str
    disponivel: Optional[int] = 1
    categoria_id: Optional[int] = None  
    imagem_url: Optional[str] = ""

class CategoriaSchema(BaseModel):
    nome: str

class FornecedorSchema(BaseModel):
    nome_fantasia: Optional[str] = None
    nome: Optional[str] = None
    cnpj: str
    telefone: str
    email: Optional[str] = None
    localidade: str
    nome_contato: Optional[str] = None

class VendaSchema(BaseModel):
    comprador: str
    produto_id: Optional[int] = None
    quantidade: int
    preco_total: float


# ─────────────────────────────────────────────────────────────────────────────
# ROTAS PÚBLICAS & AUTENTICAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def pagina_inicial(request: Request, db: Session = Depends(get_db)):
    produtos_do_banco = []
    if Produto:
        try:
            produtos_do_banco = db.query(Produto).all()
        except Exception as e:
            print(f"❌ Erro ao buscar produtos no banco: {e}")
        
    return templates.TemplateResponse(
        request=request, 
        name="base.html",
        context={"produtos": produtos_do_banco}
    )


@app.get("/visualizacao", response_class=HTMLResponse)
async def pagina_visualizacao(request: Request, db: Session = Depends(get_db)):
    produtos_do_banco = []
    if Produto:
        try:
            produtos_do_banco = db.query(Produto).all()
        except Exception:
            pass
    return templates.TemplateResponse(
        request=request, 
        name="public/visualizacao.html", 
        context={"produtos": produtos_do_banco}
    )


# ─────────────────────────────────────────────────────────────────────────────
# NOTA: As rotas de autenticação (POST /api/auth/login, GET /login, GET /admin)
# estão centralizadas no arquivo app/routers/auth_router.py
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# ROTAS DO PAINEL ADMINISTRATIVO
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def pagina_dashboard(request: Request, db: Session = Depends(get_db)):
    total_produtos = 0
    total_categorias = 0
    total_fornecedores = 0
    vendas_formatadas = []
    total_vendas_valor = 0.0

    try:
        if Produto:
            total_produtos = db.query(Produto).count()
        if Categoria:
            total_categorias = db.query(Categoria).count()
        if Fornecedor:
            total_fornecedores = db.query(Fornecedor).count()
        
        if Venda:
            vendas_do_banco = db.query(Venda).order_by(Venda.id.desc()).all()
            total_vendas_valor = sum(venda.preco_total for venda in vendas_do_banco)
            
            vendas_recentes = vendas_do_banco[:5]
            for v in vendas_recentes:
                nome_produto = "Produto Indisponível"
                if Produto:
                    prod = db.query(Produto).filter(Produto.id == v.produto_id).first()
                    if prod:
                        nome_produto = prod.nome
                
                vendas_formatadas.append({
                    "id": v.id,
                    "comprador": v.comprador,
                    "produto_nome": nome_produto,
                    "quantidade": v.quantidade,
                    "preco_total": v.preco_total,
                    "data_venda": getattr(v, "data_venda", "")
                })
    except Exception as e:
        print(f"⚠️ Alerta: Erro ao carregar Visão Geral: {e}")

    faturamento_pt_br = f"{total_vendas_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return templates.TemplateResponse(
        request=request,
        name="admin/visaogeral.html",
        context={
            "total_produtos": total_produtos,
            "total_categorias": total_categorias,
            "total_fornecedores": total_fornecedores,
            "faturamento_total": faturamento_pt_br,
            "vendas_recentes": vendas_formatadas
        }
    )


@app.get("/dashboard/visaogeral")
async def redirecionar_visaogeral():
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard/produtos", response_class=HTMLResponse)
async def pagina_dashboard_produtos(request: Request, db: Session = Depends(get_db)):
    produtos_do_banco = []
    categorias_do_banco = []
    try:
        if Produto:
            produtos_do_banco = db.query(Produto).all()
        if Categoria:
            categorias_do_banco = db.query(Categoria).all()  
    except Exception:
        pass

    return templates.TemplateResponse(
        request=request,
        name="admin/produtos.html",
        context={
            "produtos": produtos_do_banco,
            "categorias": categorias_do_banco  
        }
    )


@app.get("/dashboard/categorias", response_class=HTMLResponse)
async def pagina_dashboard_categorias(request: Request, db: Session = Depends(get_db)):
    categorias_do_banco = []
    categorias_serializadas = []
    try:
        if Categoria:
            categorias_do_banco = db.query(Categoria).all()
            categorias_serializadas = [{"id": cat.id, "nome": cat.nome} for cat in categorias_do_banco]
    except Exception:
        pass

    return templates.TemplateResponse(
        request=request,
        name="admin/categorias.html",
        context={
            "categories": categorias_do_banco,
            "categorias": categorias_do_banco,
            "categorias_json": categorias_serializadas
        }
    )


@app.get("/dashboard/fornecedores", response_class=HTMLResponse)
async def pagina_dashboard_fornecedores(request: Request, db: Session = Depends(get_db)):
    fornecedores_do_banco = []
    fornecedores_serializados = []
    try:
        if Fornecedor:
            fornecedores_do_banco = db.query(Fornecedor).all()
            fornecedores_serializados = [
                {
                    "id": f.id,
                    "nome_fantasia": getattr(f, "nome_fantasia", getattr(f, "nome", "")),
                    "cnpj": f.cnpj,
                    "telefone": f.telefone,
                    "email": f.email,
                    "localidade": getattr(f, "localidade", ""),
                    "nome_contato": getattr(f, "nome_contato", "")
                }
                for f in fornecedores_do_banco
            ]
    except Exception:
        pass
    
    return templates.TemplateResponse(
        request=request, 
        name="admin/fornecedores.html",
        context={
            "fornecedores": fornecedores_do_banco,
            "fornecedores_json": fornecedores_serializados
        }
    )


@app.get("/dashboard/vendas", response_class=HTMLResponse)
async def pagina_dashboard_vendas(request: Request, db: Session = Depends(get_db)):
    produtos_do_banco = []
    vendas_formatadas = []
    faturamento_calculado = 0.0
    
    try:
        if Produto:
            produtos_do_banco = db.query(Produto).filter(Produto.disponivel == True).all()
        if Venda:
            vendas_do_banco = db.query(Venda).order_by(Venda.id.desc()).all()
            for v in vendas_do_banco:
                nome_produto = "Produto Indisponível"
                if Produto:
                    prod = db.query(Produto).filter(Produto.id == v.produto_id).first()
                    if prod:
                        nome_produto = prod.nome
                faturamento_calculado += v.preco_total
                
                vendas_formatadas.append({
                    "id": v.id,
                    "comprador": v.comprador,
                    "produto_name": nome_produto,
                    "quantidade": v.quantidade,
                    "preco_total": v.preco_total,
                    "data_venda": getattr(v, "data_venda", "")
                })
    except Exception:
        pass
    
    return templates.TemplateResponse(
        request=request, 
        name="admin/vendas.html",
        context={
            "produtos": produtos_do_banco,
            "vendas": vendas_formatadas,
            "faturamento_total": f"{faturamento_calculado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        }
    )


# ─────────────────────────────────────────────────────────────────────────────
# API REST (ENDPOINTS CRUD)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/admin/assets/imagens")
async def listar_imagens_galeria():
    caminho_pasta = os.path.join(caminho_static_correto, "assets")
    if not os.path.exists(caminho_pasta):
        os.makedirs(caminho_pasta)
        return {"imagens": []}
        
    try:
        extensoes_permitidas = (".png", ".jpg", ".jpeg", ".svg", ".webp")
        arquivos = os.listdir(caminho_pasta)
        
        imagens = [
            f"/static/assets/{arq}" 
            for arq in arquivos 
            if arq.lower().endswith(extensoes_permitidas)
        ]
        return {"imagens": sorted(imagens)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler pasta de mídias: {str(e)}")


# --- CRUD PRODUTOS ---

@app.post("/admin/produtos")
async def criar_produto(dados: ProdutoSchema, db: Session = Depends(get_db)):
    if not Produto:
        raise HTTPException(status_code=501, detail="Modelo Produto não configurado.")
    novo = Produto(
        nome         = dados.nome,
        preco        = dados.preco,
        tamanho      = dados.tamanho,
        disponivel   = bool(dados.disponivel),
        categoria_id = dados.categoria_id,  
        imagem_url   = dados.imagem_url
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"status": "criado", "id": novo.id}


@app.put("/admin/produtos/{produto_id}")
async def atualizar_produto(produto_id: int, dados: ProdutoSchema, db: Session = Depends(get_db)):
    if not Produto:
        raise HTTPException(status_code=501, detail="Modelo Produto não configurado.")
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    
    produto.nome = dados.nome
    produto.preco = dados.preco
    produto.tamanho = dados.tamanho
    produto.disponivel = bool(dados.disponivel)
    produto.categoria_id = dados.categoria_id  
    produto.imagem_url = dados.imagem_url
    
    db.commit()
    return {"status": "atualizado"}


@app.delete("/admin/produtos/{produto_id}")
async def deletar_produto(produto_id: int, db: Session = Depends(get_db)):
    if not Produto:
        raise HTTPException(status_code=501, detail="Modelo Produto não configurado.")
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
        
    db.delete(produto)
    db.commit()
    return {"status": "deletado"}


# --- CRUD CATEGORIAS ---

@app.post("/admin/categorias")
async def criar_categoria(dados: CategoriaSchema, db: Session = Depends(get_db)):
    if not Categoria:
        raise HTTPException(status_code=501, detail="Módulo Categoria ainda não foi implementado.")
    nova = Categoria(nome=dados.nome)
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return {"status": "criado", "id": nova.id}


@app.put("/admin/categorias/{categoria_id}")
async def atualizar_categoria(categoria_id: int, dados: CategoriaSchema, db: Session = Depends(get_db)):
    if not Categoria:
        raise HTTPException(status_code=501, detail="Módulo Categoria ainda não foi implementado.")
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    
    categoria.nome = dados.nome
    db.commit()
    return {"status": "atualizado"}


@app.delete("/admin/categorias/{categoria_id}")
async def deletar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    if not Categoria:
        raise HTTPException(status_code=501, detail="Módulo Categoria ainda não foi implementado.")
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    
    try:
        db.delete(categoria)
        db.commit()
        return {"status": "deletado"}
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=400, 
            detail="Não é possível deletar esta categoria pois existem produtos vinculados a ela."
        )


# --- CRUD FORNECEDORES ---

@app.post("/admin/fornecedores")
async def criar_fornecedor(dados: FornecedorSchema, db: Session = Depends(get_db)):
    if not Fornecedor:
        raise HTTPException(status_code=501, detail="Módulo Fornecedor ainda não foi implementado.")
    cnpj_existente = db.query(Fornecedor).filter(Fornecedor.cnpj == dados.cnpj).first()
    if cnpj_existente:
        raise HTTPException(status_code=400, detail="Já existe um fornecedor cadastrado com este CNPJ.")

    nome_final = dados.nome_fantasia if dados.nome_fantasia else dados.nome
    if not nome_final:
        raise HTTPException(status_code=422, detail="O nome do fornecedor é obrigatório.")

    dados_mapeados = {
        "cnpj": dados.cnpj,
        "telefone": dados.telefone,
        "email": dados.email,
        "nome_contato": dados.nome_contato,
        "contato": dados.nome_contato,
        "localidade": dados.localidade,
        "endereco": dados.localidade,
        "cidade": dados.localidade
    }

    if hasattr(Fornecedor, "nome_empresa"):
        dados_mapeados["nome_empresa"] = nome_final
    if hasattr(Fornecedor, "nome_fantasia"):
        dados_mapeados["nome_fantasia"] = nome_final
    if hasattr(Fornecedor, "nome"):
        dados_mapeados["nome"] = nome_final

    campos_validos = {}
    for chave, valor in dados_mapeados.items():
        if hasattr(Fornecedor, chave) and valor is not None:
            campos_validos[chave] = valor

    novo = Fornecedor(**campos_validos)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"status": "criado", "id": novo.id}


@app.put("/admin/fornecedores/{fornecedor_id}")
async def atualizar_fornecedor(fornecedor_id: int, dados: FornecedorSchema, db: Session = Depends(get_db)):
    if not Fornecedor:
        raise HTTPException(status_code=501, detail="Módulo Fornecedor ainda não foi implementado.")
    fornecedor = db.query(Fornecedor).filter(Fornecedor.id == fornecedor_id).first()
    if not fornecedor: 
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    
    nome_final = dados.nome_fantasia if dados.nome_fantasia else dados.nome

    dados_mapeados = {
        "cnpj": dados.cnpj,
        "telefone": dados.telefone,
        "email": dados.email,
        "nome_contato": dados.nome_contato,
        "contato": dados.nome_contato,
        "localidade": dados.localidade,
        "endereco": dados.localidade,
        "cidade": dados.localidade
    }

    if nome_final:
        dados_mapeados["nome_empresa"] = nome_final
        dados_mapeados["nome_fantasia"] = nome_final
        dados_mapeados["nome"] = nome_final

    for chave, valor in dados_mapeados.items():
        if hasattr(fornecedor, chave) and valor is not None:
            setattr(fornecedor, chave, valor)
    
    db.commit()
    return {"status": "atualizado"}


@app.delete("/admin/fornecedores/{fornecedor_id}")
@app.post("/admin/fornecedores/{fornecedor_id}/deletar")
async def deletar_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    if not Fornecedor:
        raise HTTPException(status_code=501, detail="Módulo Fornecedor ainda não foi implementado.")
    fornecedor = db.query(Fornecedor).filter(Fornecedor.id == fornecedor_id).first()
    if not fornecedor:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    
    try:
        if Produto and hasattr(Produto, 'fornecedor_id'):
            produtos_vinculados = db.query(Produto).filter(Produto.fornecedor_id == fornecedor_id).all()
            for prod in produtos_vinculados:
                prod.fornecedor_id = None 
        
        db.delete(fornecedor)
        db.commit()
        return {"status": "deletado"}
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erro crítico ao deletar fornecedor: {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Não foi possível deletar o fornecedor devido a restrições no banco de dados. Erro: {str(e)}"
        )


# --- CRUD VENDAS ---

@app.post("/admin/vendas")
async def registrar_venda(dados: VendaSchema, db: Session = Depends(get_db)):
    if not Venda:
        raise HTTPException(status_code=501, detail="Módulo de vendas não está ativo no sistema.")

    if dados.produto_id and Produto:
        produto = db.query(Produto).filter(Produto.id == dados.produto_id).first()
        if not produto:
            raise HTTPException(status_code=404, detail="Produto vendido não encontrado no sistema.")

    nova_venda = Venda(
        comprador=dados.comprador,
        produto_id=dados.produto_id,
        quantidade=dados.quantidade,
        preco_total=dados.preco_total
    )
    
    db.add(nova_venda)
    db.commit()
    db.refresh(nova_venda)
    return {"status": "criado", "id": nova_venda.id}


@app.put("/admin/vendas/{venda_id}")
async def atualizar_venda(venda_id: int, dados: VendaSchema, db: Session = Depends(get_db)):
    if not Venda:
        raise HTTPException(status_code=501, detail="Módulo de vendas não está ativo no sistema.")

    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Registro de venda não encontrado.")
    
    venda.comprador = dados.comprador
    venda.quantidade = dados.quantidade
    venda.preco_total = dados.preco_total
    
    if dados.produto_id:
        venda.produto_id = dados.produto_id

    db.commit()
    return {"status": "atualizado"}


@app.delete("/admin/vendas/{venda_id}")
async def deletar_venda(venda_id: int, db: Session = Depends(get_db)):
    if not Venda:
        raise HTTPException(status_code=501, detail="Módulo de vendas não está ativo no sistema.")

    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")
        
    db.delete(venda)
    db.commit()
    return {"status": "deletado"}


@app.get("/admin/vendas/{venda_id}/extrato")
async def gerar_extrato_venda(venda_id: int, db: Session = Depends(get_db)):
    if not Venda:
        raise HTTPException(status_code=501, detail="Módulo de vendas não está ativo no sistema.")

    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada no banco.")
        
    nome_produto = "Produto Indisponível"
    if Produto:
        prod = db.query(Produto).filter(Produto.id == venda.produto_id).first()
        if prod:
            nome_produto = prod.nome
    
    data_formatada = ""
    if hasattr(venda, "data_venda") and venda.data_venda:
        data_formatada = venda.data_venda.strftime("%d/%m/%Y %H:%M")

    return {
        "titulo": "COMPROVANTE DE VENDA - AAPM",
        "venda_id": venda.id,
        "comprador": venda.comprador,
        "produto": nome_produto,
        "quantidade": venda.quantidade,
        "total_pago": venda.preco_total,
        "data": data_formatada
    }