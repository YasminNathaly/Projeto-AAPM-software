import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "sua-chave-secreta-muito-segura-aqui-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440


def verificar_senha(senha_plana: str, hash_senha: str) -> bool:
    if not hash_senha:
        return False

    if senha_plana == hash_senha:
        return True

    try:
        return pwd_context.verify(senha_plana, hash_senha)
    except Exception as e:
        print(f"[DEBUG AUTH] Erro ao verificar hash com Passlib: {e}")
        import bcrypt

        try:
            return bcrypt.checkpw(senha_plana.encode("utf-8"), hash_senha.encode("utf-8"))
        except Exception as err:
            print(f"[DEBUG AUTH] Erro no fallback do Bcrypt: {err}")
            return False


def gerar_hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def criar_access_token(usuario_id: int, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"sub": str(usuario_id), "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verificar_token(token: str) -> dict:
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )


def get_usuario_atual(request: Request, db: Session = None) -> Usuario:
    if db is None:
        db = next(get_db())

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


def autenticar_usuario(db: Session, credenciais):
    usuario = db.query(Usuario).filter(Usuario.email == credenciais.email).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail não encontrado no sistema",
        )

    if not verificar_senha(credenciais.senha, usuario.senha):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha incorreta",
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário inativo. Contacte a administração.",
        )

    access_token = criar_access_token(usuario_id=usuario.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario_id": usuario.id,
        "usuario_nome": usuario.nome,
    }


def registrar_usuario(db: Session, dados):
    usuario_existente = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já cadastrado no sistema",
        )

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha=gerar_hash_senha(dados.senha),
        role=getattr(dados, "role", "FUNCIONARIO"),
        ativo=True,
    )

    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)

    access_token = criar_access_token(usuario_id=novo_usuario.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario_id": novo_usuario.id,
        "usuario_nome": novo_usuario.nome,
    }
