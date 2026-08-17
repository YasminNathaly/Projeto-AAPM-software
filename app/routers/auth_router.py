"""
Router de Autenticação da AAPM
Responsável por login, logout e gerenciamento de sessões
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import JWTError, jwt
import os

from app.database import get_db
from app.models.usuario import Usuario
from passlib.context import CryptContext

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

def verificar_senha(senha_plana: str, hash_senha: str) -> bool:
    """
    Verifica se a senha coincide com o hash armazenado.
    Possui fallback para texto puro caso existam senhas antigas sem hash.
    """
    try:
        return pwd_context.verify(senha_plana, hash_senha)
    except Exception:
        # Permite comparar se a senha no banco estiver salva em texto puro
        return senha_plana == hash_senha

def gerar_hash_senha(senha: str) -> str:
    """Gera um hash bcrypt para a senha"""
    return pwd_context.hash(senha)

def criar_access_token(usuario_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Cria um JWT token para o usuário"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"sub": str(usuario_id), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verificar_token(token: str) -> dict:
    """Verifica e decodifica um JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id: str = payload.get("sub")
        if usuario_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: usuário não encontrado",
            )
        return {"usuario_id": int(usuario_id)}
    except JWTError as e:
        if "expired" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
            )

def get_usuario_atual(
    request: Request,
    db: Session = Depends(get_db)
) -> Usuario:
    """Extrai e valida o usuário do header de autorização"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não fornecido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Esquema de autenticação inválido",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de autorização inválido",
        )
    
    payload = verificar_token(token)
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

@router.post("/api/auth/login", response_model=TokenSchema)
async def fazer_login(
    credenciais: UsuarioLoginSchema,
    db: Session = Depends(get_db)
):
    """
    Autentica um usuário e retorna um JWT token
    """
    # 1. Buscar usuário por e-mail
    usuario = db.query(Usuario).filter(Usuario.email == credenciais.email).first()
    
    # 2. Se o usuário não existir -> BARRA AQUI
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    
    # 3. Se a senha for incorreta -> BARRA AQUI
    if not verificar_senha(credenciais.senha, usuario.senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos",
        )
    
    # 4. Se usuário inativo -> BARRA AQUI
    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo. Contacte a administração.",
        )
    
    # 5. Só gera o token se passar por TODAS as verificações acima
    access_token = criar_access_token(usuario_id=usuario.id)
    
    return TokenSchema(
        access_token=access_token,
        token_type="bearer",
        usuario_id=usuario.id,
        usuario_nome=usuario.nome
    )

@router.post("/api/auth/logout")
async def fazer_logout(
    current_user: Usuario = Depends(get_usuario_atual)
):
    """
    Realiza logout do usuário
    """
    return {
        "status": "sucesso",
        "mensagem": "Logout realizado com sucesso",
        "usuario": current_user.nome
    }

@router.post("/api/auth/registrar", response_model=TokenSchema)
async def registrar_usuario(
    dados: UsuarioCadastroSchema,
    db: Session = Depends(get_db)
):
    """
    Cria um novo usuário no sistema
    """
    usuario_existente = db.query(Usuario).filter(
        Usuario.email == dados.email
    ).first()
    
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já cadastrado no sistema",
        )
    
    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha=gerar_hash_senha(dados.senha),
        role=dados.role,
        ativo=True
    )
    
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    
    access_token = criar_access_token(usuario_id=novo_usuario.id)
    
    return TokenSchema(
        access_token=access_token,
        token_type="bearer",
        usuario_id=novo_usuario.id,
        usuario_nome=novo_usuario.nome
    )

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
        "ativo": current_user.ativo
    }

# ─────────────────────────────────────────────────────────────────────────────
# ROTAS DE PÁGINAS (HTML)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def pagina_login(request: Request):
    """Retorna a página de login"""
    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )

@router.get("/admin", response_class=HTMLResponse)
async def pagina_admin(request: Request):
    """Retorna o painel administrativo"""
    return templates.TemplateResponse(
        request=request,
        name="admin/admin.html"
    )

# ─────────────────────────────────────────────────────────────────────────────
# ROTA DE VERIFICAÇÃO DE SAÚDE
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/api/auth/health")
async def verificar_saude():
    """Verifica se o servidor de autenticação está funcionando"""
    return {
        "status": "ok",
        "mensagem": "Servidor de autenticação operacional",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }