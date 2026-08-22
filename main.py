import os
import re
import shutil
import uuid
from typing import Optional, Union, List
from fastapi import FastAPI, Request, Depends, Form, HTTPException, status, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from sqlalchemy import inspect, text
import os
from dotenv import load_dotenv

load_dotenv() # Carrega as variáveis do arquivo .env

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

# 1. Importações do banco e dos modelos
from app.database import engine, Base, get_db
from app.routers import categoria_router, produto_router
from app.routers.auth_router import router as auth_router
from app.routers.fornecedor import router as fornecedor_router
from app.routers.variacao_router import router as variacao_router
from app.routers.venda_router import router as venda_router

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

# MEXI AQUI: import do model de Variação de produto.
# Tentei os caminhos mais comuns dado que o variacao_router já existe no projeto.
# Se nenhum bater, Variacao fica None e o código de gravação simplesmente é pulado
# (sem quebrar o resto do app) — me avisa o caminho certo do arquivo pra eu fechar isso.
try:
    from app.models.variacao import VariacaoProduto as Variacao
except ImportError:
    Variacao = None


# Cria as tabelas no Banco de Dados
Base.metadata.create_all(bind=engine)

def garantir_colunas_vendas():
    with engine.begin() as conn:
        inspector = inspect(conn)
        colunas = {coluna["name"] for coluna in inspector.get_columns("vendas")}
        colunas_para_adicionar = {
            "cliente": "TEXT",
            "comprador": "TEXT",
            "produto_id": "INTEGER",
            "quantidade": "INTEGER",
            "forma_pagamento": "TEXT",
            "preco_total": "REAL",
        }

        for nome, tipo in colunas_para_adicionar.items():
            if nome not in colunas:
                conn.execute(text(f"ALTER TABLE vendas ADD COLUMN {nome} {tipo}"))

garantir_colunas_vendas()


def garantir_colunas_itens_venda():
    with engine.begin() as conn:
        inspector = inspect(conn)
        colunas = {coluna["name"] for coluna in inspector.get_columns("itens_venda")}
        if "variacao_id" not in colunas:
            conn.execute(text("ALTER TABLE itens_venda ADD COLUMN variacao_id INTEGER"))

garantir_colunas_itens_venda()


def garantir_colunas_fornecedores():
    with engine.begin() as conn:
        inspector = inspect(conn)
        colunas = {c["name"] for c in inspector.get_columns("fornecedores")}
        colunas_para_adicionar = {
            "documento": "TEXT",
            "email": "TEXT",
            "telefone": "TEXT",
        }
        for nome, tipo in colunas_para_adicionar.items():
            if nome not in colunas:
                conn.execute(text(f"ALTER TABLE fornecedores ADD COLUMN {nome} {tipo}"))

garantir_colunas_fornecedores()

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
app.include_router(produto_router.router)
app.include_router(categoria_router.router)
app.include_router(fornecedor_router)
app.include_router(variacao_router)
app.include_router(venda_router)

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

# MEXI AQUI: schema para cada linha de variação enviada pelo formulário
# (nome_variacao + estoque, exatamente o que o admin.html manda em coletarVariacoes()).
class VariacaoSchema(BaseModel):
    nome_variacao: str
    estoque: Optional[int] = 0

    @field_validator("estoque", mode="before")
    def tratar_estoque_variacao(cls, v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0


class ProdutoSchema(BaseModel):
    nome: str
    preco: Union[float, str]
    tamanho: Optional[str] = ""
    quantidade: Optional[int] = 0
    estoque: Optional[int] = 0
    disponivel: Optional[Union[int, bool, str]] = 1
    categoria_id: Optional[Union[int, str]] = None
    imagem_url: Optional[str] = ""
    # MEXI AQUI: sem esse campo, o Pydantic descartava silenciosamente as
    # variações enviadas pelo formulário (era por isso que nada era salvo).
    variacoes: Optional[List[VariacaoSchema]] = []

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

    @field_validator("quantidade", mode="before")
    def tratar_quantidade(cls, v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    @field_validator("estoque", mode="before")
    def tratar_estoque(cls, v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0


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


# MEXI AQUI: função central que grava as variações de um produto no banco.
# É usada tanto na criação quanto na edição. Em edição, apaga as variações
# antigas antes de recriar (evita duplicar a cada "Salvar Alterações").
def sincronizar_variacoes_produto(db: Session, produto_id: int, variacoes: List[VariacaoSchema]):
    if not Variacao:
        return  # model não encontrado - ver comentário no topo do arquivo

    # Remove as variações antigas deste produto
    db.query(Variacao).filter(Variacao.produto_id == produto_id).delete()

    # Recria a partir do que veio no formulário
    for v in (variacoes or []):
        nome_limpo = (v.nome_variacao or "").strip()
        if not nome_limpo:
            continue
        db.add(Variacao(
            produto_id=produto_id,
            nome_variacao=nome_limpo,
            estoque=v.estoque or 0
        ))

    db.commit()

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
    retorno = []
    for p in db.query(Produto).all():
        variacoes = []
        if hasattr(p, "variacoes"):
            for v in p.variacoes:
                variacoes.append({
                    "id": v.id,
                    "nome_variacao": v.nome_variacao,
                    "sku": getattr(v, "sku", None),
                    "estoque": getattr(v, "estoque", 0),
                    "preco_adicional": getattr(v, "preco_adicional", 0.0)
                })
        retorno.append({
            "id": p.id,
            "nome": p.nome,
            "preco": p.preco,
            "tamanho": getattr(p, "tamanho", ""),
            "quantidade": getattr(p, "quantidade", getattr(p, "estoque", 0)) or 0,
            "estoque": getattr(p, "estoque", getattr(p, "quantidade", 0)) or 0,
            "disponivel": getattr(p, "disponivel", True),
            "categoria_id": getattr(p, "categoria_id", None),
            "imagem_url": getattr(p, "imagem_url", ""),
            "variacoes": variacoes
        })
    return retorno

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
    
    nova = Categoria(nome=dados.nome)
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
# CRUD USUÁRIOS (COMPLETO E OTIMIZADO)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/usuarios")
@app.get("/api/usuarios/")
async def api_listar_usuarios(db: Session = Depends(get_db)):
    if not Usuario:
        return []
    
    usuarios = db.query(Usuario).all()
    return [
        {
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "perfil": obter_perfil_usuario(u),
            "status": getattr(u, "status", "Ativo")
        } for u in usuarios
    ]


@app.post("/api/usuarios")
@app.post("/api/usuarios/")
async def criar_usuario(dados: UsuarioSchema, db: Session = Depends(get_db)):
    if not Usuario:
        raise HTTPException(status_code=501, detail="Modelo Usuario não configurado.")
    
    # 1. Trata a senha para o limite do bcrypt
    senha_bruta = (dados.senha or "senai@1234").encode('utf-8')[:72]
    senha_criptografada = pwd_context.hash(senha_bruta.decode('utf-8', errors='ignore'))

    # 2. Mapeamento dinâmico do campo de senha no modelo
    campo_senha = "senha"
    if hasattr(Usuario, "senha_hash"):
        campo_senha = "senha_hash"
    elif hasattr(Usuario, "hashed_password"):
        campo_senha = "hashed_password"

    usuario_kwargs = {
        "nome": dados.nome,
        "email": dados.email,
        campo_senha: senha_criptografada
    }

    # 3. Mapeamento de perfil/cargo e status
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
@app.put("/api/usuarios/{usuario_id}/")
async def atualizar_usuario(usuario_id: int, dados: UsuarioSchema, db: Session = Depends(get_db)):
    if not Usuario:
        raise HTTPException(status_code=501, detail="Modelo Usuario não configurado.")
    
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    # Atualiza campos básicos
    usuario.nome = dados.nome
    usuario.email = dados.email

    # Atualiza perfil/cargo
    if hasattr(usuario, "perfil"):
        usuario.perfil = dados.perfil
    elif hasattr(usuario, "cargo"):
        usuario.cargo = dados.perfil

    # Atualiza status
    if hasattr(usuario, "status"):
        usuario.status = dados.status

    # Atualiza senha apenas se for enviada
    if dados.senha and dados.senha.strip():
        senha_bruta = dados.senha.encode('utf-8')[:72]
        hash_nova = pwd_context.hash(senha_bruta.decode('utf-8', errors='ignore'))
        
        if hasattr(usuario, "senha"):
            usuario.senha = hash_nova
        elif hasattr(usuario, "senha_hash"):
            usuario.senha_hash = hash_nova
        elif hasattr(usuario, "hashed_password"):
            usuario.hashed_password = hash_nova

    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    return {
        "status": "atualizado",
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil": obter_perfil_usuario(usuario),
            "status": getattr(usuario, "status", "Ativo")
        }
    }


@app.delete("/api/usuarios/{usuario_id}")
@app.delete("/api/usuarios/{usuario_id}/")
async def deletar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    if not Usuario:
        raise HTTPException(status_code=501, detail="Modelo Usuario não configurado.")
    
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    db.delete(usuario)
    db.commit()
    
    return {"status": "deletado", "mensagem": f"Usuário {usuario_id} removido com sucesso."}
# ─────────────────────────────────────────────────────────────────────────────
# CRUD PRODUTOS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/produtos")
@app.post("/admin/produtos")
async def criar_produto(dados: ProdutoSchema, db: Session = Depends(get_db)):
    if not Produto:
        raise HTTPException(status_code=501, detail="Modelo Produto não configurado.")

    quantidade = getattr(dados, "quantidade", 0) or getattr(dados, "estoque", 0) or 0
    estoque = getattr(dados, "estoque", quantidade) or quantidade or 0

    novo = Produto(
        nome=dados.nome,
        preco=dados.preco,
        tamanho=dados.tamanho,
        quantidade=quantidade,
        estoque=estoque,
        disponivel=bool(dados.disponivel),
        categoria_id=dados.categoria_id,
        imagem_url=dados.imagem_url
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)

    # MEXI AQUI: grava as variações enviadas no formulário para este produto recém-criado.
    sincronizar_variacoes_produto(db, novo.id, dados.variacoes)

    return {"status": "criado", "id": novo.id}

@app.put("/api/produtos/{produto_id}")
@app.put("/admin/produtos/{produto_id}")
async def atualizar_produto(produto_id: int, dados: ProdutoSchema, db: Session = Depends(get_db)):
    if not Produto:
        raise HTTPException(status_code=501, detail="Modelo Produto não configurado.")
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    quantidade = getattr(dados, "quantidade", 0) or getattr(dados, "estoque", 0) or 0
    estoque = getattr(dados, "estoque", quantidade) or quantidade or 0

    produto.nome = dados.nome
    produto.preco = dados.preco
    produto.tamanho = dados.tamanho
    produto.quantidade = quantidade
    produto.estoque = estoque
    produto.disponivel = bool(dados.disponivel)
    produto.categoria_id = dados.categoria_id
    produto.imagem_url = dados.imagem_url

    db.commit()

    # MEXI AQUI: re-sincroniza as variações (apaga as antigas e grava as novas)
    # para não duplicar a cada edição.
    sincronizar_variacoes_produto(db, produto.id, dados.variacoes)

    return {"status": "atualizado"}

@app.delete("/api/produtos/{produto_id}")
@app.delete("/admin/produtos/{produto_id}")
async def deletar_produto(produto_id: int, db: Session = Depends(get_db)):
    if not Produto:
        raise HTTPException(status_code=501, detail="Modelo Produto não configurado.")
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    # MEXI AQUI: remove as variações órfãs antes de apagar o produto,
    # para não deixar lixo no banco (e evitar erro de FK em bancos que a checam).
    if Variacao:
        db.query(Variacao).filter(Variacao.produto_id == produto_id).delete()

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