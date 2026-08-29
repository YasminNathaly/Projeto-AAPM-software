"""
Router de Autenticação da AAPM
Responsável por login, logout e gerenciamento de sessões
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os

from app.controllers import usuario_controller
from app.database import get_db
from app.models.usuario import Usuario

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter()

# Chave secreta para JWT (em produção, use uma variável de ambiente)
SECRET_KEY = os.getenv("SECRET_KEY", "sua-chave-secreta-muito-segura-aqui-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 horas

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class UsuarioLoginSchema(BaseModel):
    """Schema para login de usuário"""
    email: str
    senha: str

class UsuarioCadastroSchema(BaseModel):
    """Schema para cadastro de usuário"""
    nome: str
    email: str
    senha: str
    role: str = "FUNCIONARIO"

class TokenSchema(BaseModel):
    """Schema para resposta de token"""
    access_token: str
    token_type: str
    usuario_id: int
    usuario_nome: str

class TokenPayload(BaseModel):
    """Schema para payload do JWT"""
    sub: int
    exp: datetime

# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES AUXILIARES
# ─────────────────────────────────────────────────────────────────────────────

def get_usuario_atual(
    request: Request,
    db: Session = Depends(get_db)
) -> Usuario:
    """Extrai e valida o usuário do header de autorização ou do cookie do navegador."""
    token = None

    auth_header = request.headers.get("Authorization")
    if auth_header:
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                raise ValueError
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Formato de autorização inválido",
            )
    else:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não fornecido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = usuario_controller.verificar_token(token)
    usuario_id = payload.get("usuario_id")
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )

    return usuario

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS DE AUTENTICAÇÃO
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/api/auth/login")
async def fazer_login(
    credenciais: UsuarioLoginSchema,
    db: Session = Depends(get_db)
):
    token_data = usuario_controller.autenticar_usuario(db, credenciais)
    response = JSONResponse(content={
        "access_token": token_data["access_token"],
        "token_type": token_data["token_type"],
        "usuario_id": token_data["usuario_id"],
        "usuario_nome": token_data["usuario_nome"],
    })
    response.set_cookie(
        key="access_token",
        value=token_data["access_token"],
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@router.post("/api/auth/logout")
async def fazer_logout(
    current_user: Usuario = Depends(get_usuario_atual)
):
    response = JSONResponse({
        "status": "sucesso",
        "mensagem": "Logout realizado com sucesso",
        "usuario": current_user.nome,
    })
    response.delete_cookie("access_token", path="/")
    return response


@router.post("/api/auth/registrar", response_model=TokenSchema)
async def registrar_usuario(
    dados: UsuarioCadastroSchema,
    db: Session = Depends(get_db)
):
    """
    Cria um novo usuário no sistema
    """
    return usuario_controller.registrar_usuario(db, dados)

@router.get("/api/auth/me")
async def obter_usuario_atual(
    current_user: Usuario = Depends(get_usuario_atual)
):
    """
    Retorna informações do usuário autenticado
    """
    return {
        "id": current_user.id,
        "nome": current_user.nome,
        "email": current_user.email,
        "role": current_user.role,
        "ativo": current_user.ativo,
    }

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS DE PÁGINAS (HTML)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def pagina_login(request: Request):
    """Retorna a página de login"""
    return templates.TemplateResponse(request=request, name="login.html")


@router.get("/admin", response_class=HTMLResponse)
async def pagina_admin(request: Request, db: Session = Depends(get_db)):
    """Retorna o painel administrativo apenas para usuários autenticados."""
    try:
        get_usuario_atual(request, db)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request=request, name="admin/admin.html")


# ─────────────────────────────────────────────────────────────────────────────
# ROTA DE VERIFICAÇÃO DE SAÚDE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/auth/health")
async def verificar_saude():
    """Verifica se o servidor de autenticação está funcionando"""
    return {
        "status": "ok",
        "mensagem": "Servidor de autenticação operacional",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

# ── Adicione estes 2 schemas junto aos outros (perto de UsuarioLoginSchema) ──

class EsqueciSenhaSchema(BaseModel):
    email: str


class RedefinirSenhaSchema(BaseModel):
    email: str
    code: str
    new_password: str


# ── Adicione estas 2 rotas junto às outras rotas de /api/auth/... ──

@router.post("/api/auth/forgot-password")
async def esqueci_senha(
    dados: EsqueciSenhaSchema,
    db: Session = Depends(get_db)
):
    """
    Sempre responde 200 com mensagem genérica, exista ou não o e-mail,
    para não revelar quais e-mails estão cadastrados no sistema.
    """
    usuario_controller.solicitar_reset_senha(db, dados.email)
    return {"message": "Se o e-mail estiver cadastrado, você receberá o código em instantes."}


@router.post("/api/auth/reset-password")
async def redefinir_senha_rota(
    dados: RedefinirSenhaSchema,
    db: Session = Depends(get_db)
):
    usuario_controller.redefinir_senha(db, dados.email, dados.code, dados.new_password)
    return {"message": "Senha redefinida com sucesso."}