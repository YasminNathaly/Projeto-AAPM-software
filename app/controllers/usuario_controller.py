import os
import hashlib
import hmac
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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

CODE_EXPIRATION_MINUTES = 15
CODE_LENGTH = 6

# Config do e-mail (Gmail SMTP). Defina essas 3 variáveis de ambiente no seu .env:
#   SMTP_EMAIL=seuemail@gmail.com
#   SMTP_APP_PASSWORD=xxxxxxxxxxxxxxxx   <- App Password do Gmail, não a senha normal
#   SMTP_FROM_NAME=AAPM SENAI Brás
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "AAPM SENAI Brás")


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


# ─────────────────────────────────────────────────────────────────────────────
# RECUPERAÇÃO DE SENHA ("Esqueci minha senha")
# ─────────────────────────────────────────────────────────────────────────────

def gerar_codigo_numerico(tamanho: int = CODE_LENGTH) -> str:
    """Gera um código numérico criptograficamente seguro, ex: '048213'."""
    return "".join(secrets.choice("0123456789") for _ in range(tamanho))


def hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


def codigos_conferem(codigo_informado: str, hash_salvo: str) -> bool:
    return hmac.compare_digest(hash_codigo(codigo_informado), hash_salvo)


def enviar_email_codigo(destinatario: str, codigo: str) -> None:
    """Envia o código de verificação por e-mail via Gmail SMTP, em HTML formatado."""
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        print(f"[AVISO] SMTP não configurado. Código gerado para {destinatario}: {codigo}")
        return

    texto_simples = (
        f"Olá,\n\n"
        f"Recebemos uma solicitação para redefinir sua senha na AAPM.\n"
        f"Seu código de verificação é: {codigo}\n\n"
        f"Este código expira em {CODE_EXPIRATION_MINUTES} minutos.\n"
        f"Se você não solicitou isso, ignore este e-mail."
    )

    html = f"""\
<!DOCTYPE html>
<html lang="pt-BR">
<body style="margin:0; padding:0; background-color:#f4f5f9; font-family: 'Segoe UI', Arial, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f9; padding: 32px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#101018; border-radius:16px; overflow:hidden;">

          <!-- Cabeçalho -->
          <tr>
            <td style="background-color:#FF0000; padding:20px 32px;">
              <span style="font-family: Arial, sans-serif; font-weight:900; font-style:italic; font-size:22px; color:#ffffff; letter-spacing:1px;">SENAI</span>
              <span style="font-family: Arial, sans-serif; font-size:16px; color:#ffffff; letter-spacing:2px; margin-left:10px; border-left:1px solid rgba(255,255,255,0.5); padding-left:10px;">AAPM</span>
            </td>
          </tr>

          <!-- Corpo -->
          <tr>
            <td style="padding:32px;">
              <span style="display:inline-block; background:rgba(214,50,80,0.12); border:1px solid rgba(214,50,80,0.3); color:#d63250; padding:4px 10px; border-radius:999px; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px;">
                Recuperação de senha
              </span>

              <h1 style="color:#ffffff; font-size:22px; margin:16px 0 8px 0;">Seu código de verificação</h1>
              <p style="color:rgba(255,255,255,0.64); font-size:14px; line-height:1.6; margin:0 0 24px 0;">
                Recebemos uma solicitação para redefinir a senha da sua conta no Painel Administrativo AAPM SENAI Brás.
                Use o código abaixo para continuar:
              </p>

              <!-- Código em destaque -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="background-color:#1a1a24; border:1px solid rgba(255,255,255,0.09); border-radius:12px; padding:20px;">
                    <span style="font-family: 'Courier New', monospace; font-size:32px; font-weight:700; letter-spacing:8px; color:#ffffff;">{codigo}</span>
                  </td>
                </tr>
              </table>

              <p style="color:rgba(255,255,255,0.38); font-size:12px; margin:20px 0 0 0;">
                Este código expira em {CODE_EXPIRATION_MINUTES} minutos. Se você não solicitou essa redefinição,
                pode ignorar este e-mail com segurança — sua senha continuará a mesma.
              </p>
            </td>
          </tr>

          <!-- Rodapé -->
          <tr>
            <td style="padding:20px 32px; border-top:1px solid rgba(255,255,255,0.09);">
              <p style="color:rgba(255,255,255,0.38); font-size:11px; margin:0;">
                Este é um e-mail automático do Painel Administrativo AAPM — SENAI Brás. Não responda a esta mensagem.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Código de redefinição de senha - AAPM SENAI Brás"
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_EMAIL}>"
    msg["To"] = destinatario

    msg.attach(MIMEText(texto_simples, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    print(f"[DEBUG EMAIL] Tentando enviar de '{SMTP_EMAIL}' para '{destinatario}' | código: {codigo}")

    with smtplib.SMTP("smtp.gmail.com", 587) as servidor:
        servidor.starttls()
        servidor.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        servidor.sendmail(SMTP_EMAIL, [destinatario], msg.as_string())

    print("[DEBUG EMAIL] sendmail() concluído sem erros.")


def solicitar_reset_senha(db: Session, email: str) -> None:
    """
    Gera e envia o código de reset, se o e-mail existir.
    Não levanta exceção se o e-mail não existir (a rota sempre responde
    a mesma mensagem genérica, pra não revelar quais e-mails existem).
    """
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        return

    codigo = gerar_codigo_numerico()
    usuario.reset_code_hash = hash_codigo(codigo)
    usuario.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRATION_MINUTES)
    usuario.reset_code_used = False

    db.add(usuario)
    db.commit()

    enviar_email_codigo(usuario.email, codigo)


def redefinir_senha(db: Session, email: str, codigo: str, nova_senha: str) -> None:
    if len(nova_senha) < 8:
        raise HTTPException(status_code=422, detail="A senha deve ter no mínimo 8 caracteres.")

    usuario = db.query(Usuario).filter(Usuario.email == email).first()

    if not usuario or not usuario.reset_code_hash or not usuario.reset_code_expires_at:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    if usuario.reset_code_used:
        raise HTTPException(status_code=400, detail="Este código já foi utilizado.")

    expira_em = usuario.reset_code_expires_at
    if expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expira_em:
        raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo.")

    if not codigos_conferem(codigo, usuario.reset_code_hash):
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    usuario.senha = gerar_hash_senha(nova_senha)
    usuario.reset_code_hash = None
    usuario.reset_code_expires_at = None
    usuario.reset_code_used = True

    db.add(usuario)
    db.commit()