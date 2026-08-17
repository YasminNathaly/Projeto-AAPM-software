import os
import re
import shutil
import uuid
from typing import Optional, Union
from fastapi import FastAPI, Request, Depends, Form, HTTPException, status, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator

# 1. Importações do banco e dos modelos
from app.database import engine, Base, get_db
from app.routers.auth_router import router as auth_router

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


# Cria as tabelas no Banco de Dados
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sistema AAPM - Gestão de Estoque e Vendas",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─────────────────────────────────────────────────────────────────────────────
# CAMINHOS E STATIC
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))
caminho_static_correto = os.path.join(BASE_DIR, "app", "static")
app.mount("/static", StaticFiles(directory=caminho_static_correto), name="static")

# Pasta de uploads (fotos de produtos) dentro da própria pasta static
CAMINHO_UPLOADS = os.path.join(caminho_static_correto, "uploads")
os.makedirs(CAMINHO_UPLOADS, exist_ok=True)

app.include_router(auth_router)

# ─────────────────────────────────────────────────────────────────────────────
# EXCEÇÕES PERSONALIZADAS
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/admin") or request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": "erro", "mensagem": f"O recurso '{request.url.path}' não foi encontrado."}
        )
    return templates.TemplateResponse(request=request, name="public/404.html", status_code=404)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS PYDANTIC
# ─────────────────────────────────────────────────────────────────────────────

class ProdutoSchema(BaseModel):
    nome: str
    preco: Union[float, str]
    tamanho: Optional[str] = ""
    disponivel: Optional[Union[int, bool, str]] = 1
    categoria_id: Optional[Union[int, str]] = None
    imagem_url: Optional[str] = ""

    @field_validator("preco", mode="before")
    def tratar_preco(cls, v):
        if isinstance(v, str):
            v_limpo = re.sub(r"[^\d\.,]", "", v).replace(",", ".")
            try:
                return float(v_limpo)
            except ValueError:
                return 0.0
        return float(v) if v is not None else 0.0

    @field_validator("categoria_id", mode="before")
    def tratar_categoria(cls, v):
        if v == "" or v is None or v == "null":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("disponivel", mode="before")
    def tratar_disponivel(cls, v):
        if isinstance(v, bool):
            return 1 if v else 0
        if isinstance(v, str):
            return 1 if v.lower() in ["true", "1", "on", "yes"] else 0
        return int(v) if v is not None else 1


class CategoriaSchema(BaseModel):
    nome: str
    codigo: Optional[str] = ""
    descricao: Optional[str] = ""


class FornecedorSchema(BaseModel):
    nome: str
    documento: str
    email: Optional[str] = ""
    telefone: Optional[str] = ""


class UsuarioSchema(BaseModel):
    nome: str
    email: str
    perfil: Optional[str] = "Operador"
    senha: Optional[str] = None
    status: Optional[str] = "Ativo"


class VendaSchema(BaseModel):
    cliente: Optional[str] = "Cliente Não Informado"
    comprador: Optional[str] = None
    produto_id: int
    quantidade: Optional[int] = 1
    forma_pagamento: Optional[str] = "PIX"

# ─────────────────────────────────────────────────────────────────────────────
# AUXILIARES
# ─────────────────────────────────────────────────────────────────────────────

def obter_comprador_venda(venda_obj):
    for atributo in ["cliente", "comprador", "nome_cliente", "cliente_nome"]:
        val = getattr(venda_obj, atributo, None)
        if val and str(val).strip():
            return str(val).strip()
    return "Cliente Não Informado"

def obter_preco_total_venda(venda_obj):
    for atributo in ["valor_total", "preco_total", "total"]:
        val = getattr(venda_obj, atributo, None)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return 0.0

def obter_forma_pagamento_venda(venda_obj):
    for atributo in ["forma_pagamento", "pagamento", "forma_pgto"]:
        val = getattr(venda_obj, atributo, None)
        if val and str(val).strip():
            return str(val).strip()
    return "Não informado"

def obter_nome_produto_venda(venda_obj, db: Session):
    prod_id = getattr(venda_obj, "produto_id", getattr(venda_obj, "id_produto", None))
    if Produto and prod_id:
        prod = db.query(Produto).filter(Produto.id == prod_id).first()
        if prod and getattr(prod, "nome", None):
            return prod.nome

    for atributo in ["produto", "item", "produto_nome", "nome_produto", "descricao"]:
        valor = getattr(venda_obj, atributo, None)
        if valor and isinstance(valor, str) and valor.strip():
            return valor.strip()

    return "Produto Não Identificado"

def obter_perfil_usuario(usuario_obj):
    return getattr(usuario_obj, "perfil", getattr(usuario_obj, "cargo", getattr(usuario_obj, "funcao", getattr(usuario_obj, "tipo", "Operador"))))

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS PÚBLICAS E HTML
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def pagina_inicial(request: Request, db: Session = Depends(get_db)):
    produtos = db.query(Produto).all() if Produto else []
    return templates.TemplateResponse(request=request, name="base.html", context={"produtos": produtos})

@app.get("/visualizacao", response_class=HTMLResponse)
async def pagina_visualizacao(request: Request, db: Session = Depends(get_db)):
    produtos = db.query(Produto).all() if Produto else []
    return templates.TemplateResponse(request=request, name="public/visualizacao.html", context={"produtos": produtos})

@app.get("/dashboard", response_class=HTMLResponse)
async def pagina_dashboard(request: Request, db: Session = Depends(get_db)):
    total_produtos = db.query(Produto).count() if Produto else 0
    total_categorias = db.query(Categoria).count() if Categoria else 0
    total_fornecedores = db.query(Fornecedor).count() if Fornecedor else 0
    vendas_formatadas = []
    total_vendas_valor = 0.0

    if Venda:
        vendas_do_banco = db.query(Venda).order_by(Venda.id.desc()).all()
        total_vendas_valor = sum(obter_preco_total_venda(v) for v in vendas_do_banco)

        for v in vendas_do_banco[:5]:
            nome_prod = obter_nome_produto_venda(v, db)
            comprador = obter_comprador_venda(v)
            preco = obter_preco_total_venda(v)
            vendas_formatadas.append({
                "id": v.id,
                "comprador": comprador,
                "cliente": comprador,
                "produto_nome": nome_prod,
                "produto": nome_prod,
                "quantidade": getattr(v, "quantidade", getattr(v, "qtd", 1)),
                "preco_total": preco,
                "forma_pagamento": obter_forma_pagamento_venda(v),
                "data_venda": str(getattr(v, "data_venda", getattr(v, "created_at", "")))
            })

    faturamento_pt_br = f"{total_vendas_valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return templates.TemplateResponse(
        request=request,
        name="admin/admin.html",
        context={
            "total_produtos": total_produtos,
            "total_categorias": total_categorias,
            "total_fornecedores": total_fornecedores,
            "faturamento_total": faturamento_pt_br,
            "vendas_recentes": vendas_formatadas
        }
    )

@app.get("/dashboard/produtos", response_class=HTMLResponse)
async def pagina_dashboard_produtos(request: Request, db: Session = Depends(get_db)):
    produtos = db.query(Produto).all() if Produto else []
    categorias = db.query(Categoria).all() if Categoria else []
    return templates.TemplateResponse(request=request, name="admin/produtos.html", context={"produtos": produtos, "categorias": categorias})

@app.get("/dashboard/categorias", response_class=HTMLResponse)
async def pagina_dashboard_categorias(request: Request, db: Session = Depends(get_db)):
    categorias = db.query(Categoria).all() if Categoria else []
    return templates.TemplateResponse(request=request, name="admin/categorias.html", context={"categorias": categorias})

@app.get("/dashboard/fornecedores", response_class=HTMLResponse)
async def pagina_dashboard_fornecedores(request: Request, db: Session = Depends(get_db)):
    fornecedores = db.query(Fornecedor).all() if Fornecedor else []
    return templates.TemplateResponse(request=request, name="admin/fornecedores.html", context={"fornecedores": fornecedores})

@app.get("/dashboard/vendas", response_class=HTMLResponse)
async def pagina_dashboard_vendas(request: Request, db: Session = Depends(get_db)):
    produtos = db.query(Produto).all() if Produto else []
    vendas_formatadas = []
    faturamento = 0.0

    if Venda:
        vendas_do_banco = db.query(Venda).order_by(Venda.id.desc()).all()
        for v in vendas_do_banco:
            nome_prod = obter_nome_produto_venda(v, db)
            preco = obter_preco_total_venda(v)
            faturamento += preco
            vendas_formatadas.append({
                "id": v.id,
                "comprador": obter_comprador_venda(v),
                "produto_nome": nome_prod,
                "quantidade": getattr(v, "quantidade", getattr(v, "qtd", 1)),
                "preco_total": preco,
                "forma_pagamento": obter_forma_pagamento_venda(v),
                "data_venda": str(getattr(v, "data_venda", getattr(v, "created_at", "")))
            })

    return templates.TemplateResponse(
        request=request,
        name="admin/vendas.html",
        context={
            "produtos": produtos,
            "vendas": vendas_formatadas,
            "faturamento_total": f"{faturamento:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        }
    )

# ─────────────────────────────────────────────────────────────────────────────
# API GET ENDPOINTS (listagem)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/categorias")
async def api_listar_categorias(db: Session = Depends(get_db)):
    if not Categoria:
        return []
    return [
        {
            "id": c.id,
            "nome": c.nome,
            "codigo": getattr(c, "codigo", "") or "",
            "descricao": getattr(c, "descricao", "") or ""
        } for c in db.query(Categoria).all()
    ]

@app.get("/api/fornecedores")
async def api_listar_fornecedores(db: Session = Depends(get_db)):
    if not Fornecedor:
        return []
    return [
        {
            "id": f.id,
            "nome": f.nome,
            "documento": f.documento,
            "email": getattr(f, "email", "") or "",
            "telefone": getattr(f, "telefone", "") or ""
        } for f in db.query(Fornecedor).all()
    ]

@app.get("/api/usuarios")
async def api_listar_usuarios(db: Session = Depends(get_db)):
    if not Usuario:
        return []
    return [
        {
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "perfil": obter_perfil_usuario(u),
            "status": getattr(u, "status", "Ativo")
        } for u in db.query(Usuario).all()
    ]

@app.get("/api/produtos")
async def api_listar_produtos(db: Session = Depends(get_db)):
    if not Produto:
        return []
    return [
        {
            "id": p.id,
            "nome": p.nome,
            "preco": p.preco,
            "tamanho": getattr(p, "tamanho", ""),
            "disponivel": getattr(p, "disponivel", True),
            "categoria_id": getattr(p, "categoria_id", None),
            "imagem_url": getattr(p, "imagem_url", "")
        } for p in db.query(Produto).all()
    ]

@app.get("/api/vendas")
async def api_listar_vendas(db: Session = Depends(get_db)):
    if not Venda:
        return []
    return [
        {
            "id": v.id,
            "comprador": obter_comprador_venda(v),
            "cliente": obter_comprador_venda(v),
            "produto_id": getattr(v, "produto_id", getattr(v, "id_produto", None)),
            "produto_nome": obter_nome_produto_venda(v, db),
            "quantidade": getattr(v, "quantidade", getattr(v, "qtd", 1)),
            "preco_total": obter_preco_total_venda(v),
            "forma_pagamento": obter_forma_pagamento_venda(v),
            "data_venda": str(getattr(v, "data_venda", getattr(v, "created_at", "")))
        } for v in db.query(Venda).order_by(Venda.id.desc()).all()
    ]

# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD DE IMAGEM
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/upload-imagem")
async def upload_imagem(arquivo: UploadFile = File(...)):
    extensoes_validas = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    ext = os.path.splitext(arquivo.filename or "")[1].lower()
    if ext not in extensoes_validas:
        raise HTTPException(status_code=400, detail="Formato de imagem não suportado.")

    nome_arquivo = f"{uuid.uuid4().hex}{ext}"
    caminho_completo = os.path.join(CAMINHO_UPLOADS, nome_arquivo)

    with open(caminho_completo, "wb") as buffer:
        shutil.copyfileobj(arquivo.file, buffer)

    return {"status": "ok", "url": f"/static/uploads/{nome_arquivo}"}

# ─────────────────────────────────────────────────────────────────────────────
# CRUD CATEGORIAS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/categorias")
async def criar_categoria(dados: CategoriaSchema, db: Session = Depends(get_db)):
    if not Categoria:
        raise HTTPException(status_code=501, detail="Modelo Categoria não configurado.")
    nova = Categoria(nome=dados.nome, codigo=dados.codigo, descricao=dados.descricao)
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return {"status": "criado", "id": nova.id}

@app.put("/api/categorias/{categoria_id}")
async def atualizar_categoria(categoria_id: int, dados: CategoriaSchema, db: Session = Depends(get_db)):
    if not Categoria:
        raise HTTPException(status_code=501, detail="Modelo Categoria não configurado.")
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    categoria.nome = dados.nome
    categoria.codigo = dados.codigo
    categoria.descricao = dados.descricao
    db.commit()
    return {"status": "atualizado"}

@app.delete("/api/categorias/{categoria_id}")
async def deletar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    if not Categoria:
        raise HTTPException(status_code=501, detail="Modelo Categoria não configurado.")
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    db.delete(categoria)
    db.commit()
    return {"status": "deletado"}

# ─────────────────────────────────────────────────────────────────────────────
# CRUD FORNECEDORES
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/fornecedores")
async def criar_fornecedor(dados: FornecedorSchema, db: Session = Depends(get_db)):
    if not Fornecedor:
        raise HTTPException(status_code=501, detail="Modelo Fornecedor não configurado.")
    novo = Fornecedor(nome=dados.nome, documento=dados.documento, email=dados.email, telefone=dados.telefone)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"status": "criado", "id": novo.id}

@app.put("/api/fornecedores/{fornecedor_id}")
async def atualizar_fornecedor(fornecedor_id: int, dados: FornecedorSchema, db: Session = Depends(get_db)):
    if not Fornecedor:
        raise HTTPException(status_code=501, detail="Modelo Fornecedor não configurado.")
    fornecedor = db.query(Fornecedor).filter(Fornecedor.id == fornecedor_id).first()
    if not fornecedor:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    fornecedor.nome = dados.nome
    fornecedor.documento = dados.documento
    fornecedor.email = dados.email
    fornecedor.telefone = dados.telefone
    db.commit()
    return {"status": "atualizado"}

@app.delete("/api/fornecedores/{fornecedor_id}")
async def deletar_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    if not Fornecedor:
        raise HTTPException(status_code=501, detail="Modelo Fornecedor não configurado.")
    fornecedor = db.query(Fornecedor).filter(Fornecedor.id == fornecedor_id).first()
    if not fornecedor:
        raise HTTPException(status_code=404, detail="Fornecedor não encontrado.")
    db.delete(fornecedor)
    db.commit()
    return {"status": "deletado"}

# ─────────────────────────────────────────────────────────────────────────────
# CRUD USUÁRIOS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/usuarios")
async def criar_usuario(dados: UsuarioSchema, db: Session = Depends(get_db)):
    if not Usuario:
        raise HTTPException(status_code=501, detail="Modelo Usuario não configurado.")
    senha_hash = pwd_context.hash(dados.senha or "senai@1234")
    
    usuario_kwargs = {
        "nome": dados.nome,
        "email": dados.email,
        "senha_hash": senha_hash
    }
    
    if hasattr(Usuario, "perfil"):
        usuario_kwargs["perfil"] = dados.perfil
    elif hasattr(Usuario, "cargo"):
        usuario_kwargs["cargo"] = dados.perfil

    if hasattr(Usuario, "status"):
        usuario_kwargs["status"] = dados.status

    novo = Usuario(**usuario_kwargs)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"status": "criado", "id": novo.id}

@app.put("/api/usuarios/{usuario_id}")
async def atualizar_usuario(usuario_id: int, dados: UsuarioSchema, db: Session = Depends(get_db)):
    if not Usuario:
        raise HTTPException(status_code=501, detail="Modelo Usuario não configurado.")
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    usuario.nome = dados.nome
    usuario.email = dados.email

    if hasattr(usuario, "perfil"):
        usuario.perfil = dados.perfil
    elif hasattr(usuario, "cargo"):
        usuario.cargo = dados.perfil

    if hasattr(usuario, "status"):
        usuario.status = dados.status

    if dados.senha and hasattr(usuario, "senha_hash"):
        usuario.senha_hash = pwd_context.hash(dados.senha)
        
    db.commit()
    return {"status": "atualizado"}

@app.delete("/api/usuarios/{usuario_id}")
async def deletar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    if not Usuario:
        raise HTTPException(status_code=501, detail="Modelo Usuario não configurado.")
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    db.delete(usuario)
    db.commit()
    return {"status": "deletado"}

# ─────────────────────────────────────────────────────────────────────────────
# CRUD PRODUTOS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/produtos")
@app.post("/admin/produtos")
async def criar_produto(dados: ProdutoSchema, db: Session = Depends(get_db)):
    if not Produto:
        raise HTTPException(status_code=501, detail="Modelo Produto não configurado.")

    novo = Produto(
        nome=dados.nome,
        preco=dados.preco,
        tamanho=dados.tamanho,
        disponivel=bool(dados.disponivel),
        categoria_id=dados.categoria_id,
        imagem_url=dados.imagem_url
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"status": "criado", "id": novo.id}

@app.put("/api/produtos/{produto_id}")
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

@app.delete("/api/produtos/{produto_id}")
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

# ─────────────────────────────────────────────────────────────────────────────
# CRUD VENDAS E UTILITÁRIO
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/admin/limpar-vendas-zerar")
async def limpar_vendas_temp(db: Session = Depends(get_db)):
    if Venda:
        try:
            db.query(Venda).delete()
            db.commit()
            return {"status": "sucesso", "mensagem": "Todas as vendas antigas foram limpas do banco!"}
        except Exception as e:
            db.rollback()
            return {"status": "erro", "mensagem": str(e)}
    return {"status": "erro", "mensagem": "Modelo Venda não encontrado."}

@app.post("/api/vendas")
@app.post("/admin/vendas")
async def registrar_venda(dados: VendaSchema, db: Session = Depends(get_db)):
    if not Venda or not Produto:
        raise HTTPException(status_code=501, detail="Módulos não configurados.")

    produto = db.query(Produto).filter(Produto.id == dados.produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    preco_unitario = float(getattr(produto, "preco", 0.0))
    qtd = dados.quantidade if dados.quantidade is not None else 1
    total_calculado = preco_unitario * qtd
    nome_cliente = dados.cliente or dados.comprador or "Cliente Não Informado"

    venda_kwargs = {}

    # Cliente / Comprador
    for col in ["cliente", "comprador", "nome_cliente", "cliente_nome"]:
        if hasattr(Venda, col):
            venda_kwargs[col] = nome_cliente
            break

    # Produto
    for col in ["produto_id", "id_produto"]:
        if hasattr(Venda, col):
            venda_kwargs[col] = dados.produto_id
            break

    # Quantidade
    for col in ["quantidade", "qtd"]:
        if hasattr(Venda, col):
            venda_kwargs[col] = qtd
            break

    # Valor Total
    for col in ["valor_total", "preco_total", "total"]:
        if hasattr(Venda, col):
            venda_kwargs[col] = total_calculado
            break

    # Forma de Pagamento
    for col in ["forma_pagamento", "pagamento", "forma_pgto"]:
        if hasattr(Venda, col):
            venda_kwargs[col] = dados.forma_pagamento or "PIX"
            break

    nova_venda = Venda(**venda_kwargs)
    db.add(nova_venda)
    db.commit()
    db.refresh(nova_venda)
    return {"status": "criado", "id": nova_venda.id}

@app.delete("/api/vendas/{venda_id}")
@app.delete("/admin/vendas/{venda_id}")
async def deletar_venda(venda_id: int, db: Session = Depends(get_db)):
    if not Venda:
        raise HTTPException(status_code=501, detail="Módulo de vendas não está ativo.")

    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")

    db.delete(venda)
    db.commit()

    return {"status": "sucesso", "mensagem": f"Venda {venda_id} removida com sucesso."}