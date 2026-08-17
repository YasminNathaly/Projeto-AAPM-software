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
    Verifica a senha comparando Bcrypt, texto puro ou exceções de biblioteca.
    """
    if not hash_senha:
        return False
        
    # 1. Checagem direta de texto puro (útil se o seed salvou em texto limpo)
    if senha_plana == hash_senha:
        return True

    # 2. Tentativa via Passlib / Bcrypt
    try:
        return pwd_context.verify(senha_plana, hash_senha)
    except Exception as e:
        print(f"[DEBUG AUTH] Erro ao verificar hash com Passlib: {e}")
        # Fallback de emergência para lidar com hashes iniciados em $2a$, $2b$ ou $2y$
        import bcrypt
        try:
            return bcrypt.checkpw(senha_plana.encode('utf-8'), hash_senha.encode('utf-8'))
        except Exception as err:
            print(f"[DEBUG AUTH] Erro no fallback do Bcrypt: {err}")
            return False

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
    print(f"\n[LOGIN TRY] E-mail informado: '{credenciais.email}'")
    
    # 1. Buscar usuário por e-mail
    usuario = db.query(Usuario).filter(Usuario.email == credenciais.email).first()
    
    if not usuario:
        print(f"[LOGIN FAIL] Usuário com e-mail '{credenciais.email}' NÃO foi encontrado no banco.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail não encontrado no sistema",
        )
    
    print(f"[LOGIN INFO] Usuário encontrado: ID={usuario.id}, Nome={usuario.nome}")
    
    # 2. Verificar a senha
    senha_valida = verificar_senha(credenciais.senha, usuario.senha)
    if not senha_valida:
        print(f"[LOGIN FAIL] Senha incorreta para o e-mail '{credenciais.email}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha incorreta",
        )
    
    # 3. Validar se ativo
    if not usuario.ativo:
        print(f"[LOGIN FAIL] Usuário ID={usuario.id} está inativo.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo. Contacte a administração.",
        )
    
    # 4. Sucesso
    print(f"[LOGIN SUCCESS] Login realizado com sucesso para ID={usuario.id}")
    access_token = criar_access_token(usuario_id=usuario.id)
    
    return TokenSchema(
        access_token=access_token,
        token_type="bearer",
        usuario_id=usuario.id,
        usuario_nome=usuario.nome
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