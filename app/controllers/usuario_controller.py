import os
import hashlib
import hmac
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "sua-chave-secreta-muito-segura-aqui-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

CODE_EXPIRATION_MINUTES = 15
CODE_LENGTH = 6
RESEND_COOLDOWN_SECONDS = 60

# Config do e-mail (Gmail SMTP). Defina essas 3 variáveis de ambiente no seu .env:
#   SMTP_EMAIL=seuemail@gmail.com
#   SMTP_APP_PASSWORD=xxxxxxxxxxxxxxxx   <- App Password do Gmail, não a senha normal
#   SMTP_FROM_NAME=AAPM SENAI Brás
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "AAPM SENAI Brás")


# ─────────────────────────────────────────────────────────────────────────────
# SENHA E TOKEN
# ─────────────────────────────────────────────────────────────────────────────

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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Esquema de autenticação inválido")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Formato de autorização inválido")

    payload = verificar_token(token)
    usuario_id = payload.get("usuario_id")
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado")

    return usuario


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN / CADASTRO
# ─────────────────────────────────────────────────────────────────────────────

class _Credenciais:
    def __init__(self, email: str, senha: str):
        self.email = email
        self.senha = senha


class RegistroRequest(BaseModel):
    nome: str
    email: EmailStr
    senha: str = Field(min_length=8)
    role: Optional[str] = "FUNCIONARIO"


def autenticar_usuario(db: Session, credenciais) -> dict:
    usuario = db.query(Usuario).filter(Usuario.email == credenciais.email).first()

    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail não encontrado no sistema")

    if not verificar_senha(credenciais.senha, usuario.senha):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Senha incorreta")

    if not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo. Contacte a administração.")

    access_token = criar_access_token(usuario_id=usuario.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "usuario_id": usuario.id,
        "usuario_nome": usuario.nome,
    }


def registrar_usuario(db: Session, dados: RegistroRequest) -> dict:
    usuario_existente = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if usuario_existente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail já cadastrado no sistema")

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha=gerar_hash_senha(dados.senha),
        role=dados.role or "FUNCIONARIO",
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

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)


def gerar_codigo_numerico(tamanho: int = CODE_LENGTH) -> str:
    """Gera um código numérico criptograficamente seguro, ex: '048213'."""
    return "".join(secrets.choice("0123456789") for _ in range(tamanho))


def hash_codigo(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


def codigos_conferem(codigo_informado: str, hash_salvo: str) -> bool:
    return hmac.compare_digest(hash_codigo(codigo_informado), hash_salvo)


# Campo de estrelas fixo, usado como background-image do e-mail: pontos
# pequenos via radial-gradient + duas "nebulosas" nos tons de vermelho/roxo
# do site. Não é uma imagem de verdade, então não depende de anexo nem sofre
# bloqueio de imagem externa. Em clientes que ignoram gradients (Outlook
# desktop / Word engine), cai pra cor sólida #09090f — a mesma do site.
_ESTRELAS = [
    (6, 12), (14, 38), (9, 64), (22, 8), (30, 52), (18, 82), (38, 24),
    (44, 68), (52, 12), (60, 44), (68, 78), (74, 20), (80, 58), (88, 10),
    (92, 40), (96, 72), (4, 90), (34, 92), (58, 88), (48, 30), (26, 66),
    (70, 92), (86, 86), (12, 50), (54, 60),
]
_ESTRELAS_ROSA = [(20, 30), (66, 14), (84, 62)]


def _gerar_fundo_estrelado() -> str:
    camadas = []
    for x, y in _ESTRELAS:
        camadas.append(f"radial-gradient(1px 1px at {x}% {y}%, rgba(255,255,255,0.85), transparent 100%)")
    for x, y in _ESTRELAS_ROSA:
        camadas.append(f"radial-gradient(1.4px 1.4px at {x}% {y}%, rgba(214,50,80,0.9), transparent 100%)")
    camadas.append("radial-gradient(600px circle at 18% 12%, rgba(214,50,80,0.20), transparent 60%)")
    camadas.append("radial-gradient(520px circle at 85% 30%, rgba(125,56,62,0.16), transparent 60%)")
    camadas.append("radial-gradient(560px circle at 55% 92%, rgba(80,60,140,0.14), transparent 60%)")
    return ",\n            ".join(camadas)


FUNDO_ESTRELADO_CSS = _gerar_fundo_estrelado()


def _gerar_caixinhas_codigo(codigo: str) -> str:
    """Gera 6 células de tabela, uma por dígito, no mesmo visual dos
    .code-box do login.html (borda vermelha, monoespaçado, cantos arredondados)."""
    digitos = list(codigo.ljust(CODE_LENGTH, " "))
    celulas = []
    for digito in digitos:
        celulas.append(f"""
          <td width="46" align="center" valign="middle" class="aapm-codigo-caixa"
              style="background-color:#1a1a24; border:1px solid rgba(214,50,80,0.35);
                     border-radius:10px; height:56px; width:46px;">
            <span style="font-family:'Courier New', monospace; font-size:26px; font-weight:700; color:#ffffff;">{digito}</span>
          </td>
          <td width="8" style="font-size:0; line-height:0;">&nbsp;</td>""")
    # remove o último espaçador
    return "".join(celulas)[:-len('<td width="8" style="font-size:0; line-height:0;">&nbsp;</td>')]


def enviar_email_codigo(destinatario: str, codigo: str, nome: Optional[str] = None) -> None:
    """Envia o código de verificação por e-mail via Gmail SMTP, no mesmo
    tema escuro/estrelado usado na tela de login."""
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        print(f"[AVISO] SMTP não configurado. Código gerado para {destinatario}: {codigo}")
        return

    primeiro_nome = (nome or "").strip().split(" ")[0] if nome else ""
    saudacao = f"Olá, {primeiro_nome}," if primeiro_nome else "Olá,"

    texto_simples = (
        f"{saudacao}\n\n"
        f"Recebemos uma solicitação para redefinir sua senha na AAPM.\n"
        f"Seu código de verificação é: {codigo}\n\n"
        f"Este código expira em {CODE_EXPIRATION_MINUTES} minutos.\n"
        f"Se você não solicitou isso, ignore este e-mail."
    )

    caixinhas_codigo_html = _gerar_caixinhas_codigo(codigo)

    html = f"""\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<style>
  /* Animações CSS puras — funcionam em Apple Mail, Outlook.com e Yahoo Mail.
     Clientes que não suportam @keyframes (ex.: Gmail app em alguns casos)
     simplesmente ignoram e mostram o estado final, sem quebrar o layout. */
  @keyframes aapmPulso {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(214,50,80,0.38); }}
    50%      {{ box-shadow: 0 0 0 7px rgba(214,50,80,0.10); }}
  }}
  @keyframes aapmFadeUp {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes aapmBrilho {{
    0%, 100% {{ opacity: 1; }}
    50%      {{ opacity: 0.55; }}
  }}
  .aapm-codigo-caixa {{ animation: aapmPulso 2.4s ease-in-out infinite; }}
  .aapm-corpo {{ animation: aapmFadeUp 0.7s ease-out both; }}
  .aapm-selo-tempo {{ animation: aapmBrilho 2.8s ease-in-out infinite; }}
</style>
</head>
<body style="margin:0; padding:0; background-color:#09090f; font-family: 'Segoe UI', Arial, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#09090f;
            background-image:
            {FUNDO_ESTRELADO_CSS};
            padding: 48px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0"
               style="background-color:#101018; border:1px solid rgba(255,255,255,0.09);
                      border-radius:18px; overflow:hidden; box-shadow:0 25px 70px rgba(0,0,0,0.55);">

          <!-- Cabeçalho -->
          <tr>
            <td style="background: linear-gradient(135deg, #f3132b, #b8081b); padding:22px 32px;">
              <span style="font-family: Arial, sans-serif; font-weight:900; font-style:italic; font-size:22px; color:#ffffff; letter-spacing:1px;">SENAI</span>
              <span style="font-family: Arial, sans-serif; font-size:16px; color:#ffffff; letter-spacing:2px; margin-left:10px; border-left:1px solid rgba(255,255,255,0.5); padding-left:10px;">AAPM</span>
            </td>
          </tr>
          <!-- Filete laranja, igual ao detalhe da logo do site -->
          <tr>
            <td style="background-color:#101018; padding:0;">
              <div style="height:3px; background-color:#ff9d1f; opacity:0.9; margin:0 32px;"></div>
            </td>
          </tr>

          <!-- Corpo -->
          <tr>
            <td class="aapm-corpo" style="padding:36px 32px 28px 32px;">
              <span style="display:inline-block; background:rgba(214,50,80,0.12); border:1px solid rgba(214,50,80,0.3); color:#d63250; padding:5px 12px; border-radius:999px; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1px; margin-bottom:18px;">
                Recuperação de senha
              </span>

              <h1 style="color:#ffffff; font-size:23px; margin:16px 0 6px 0; font-weight:700;">{saudacao}</h1>
              <p style="color:rgba(255,255,255,0.64); font-size:14px; line-height:1.65; margin:0 0 26px 0;">
                Recebemos uma solicitação para redefinir a senha da sua conta no Painel Administrativo AAPM SENAI Brás.
                Use o código abaixo para continuar:
              </p>

              <!-- Código em caixinhas individuais -->
              <table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:0 auto 18px auto;">
                <tr>
                  {caixinhas_codigo_html}
                </tr>
              </table>

              <!-- Selo de expiração -->
              <table role="presentation" cellpadding="0" cellspacing="0" align="center" style="margin:0 auto 26px auto;">
                <tr>
                  <td class="aapm-selo-tempo" style="background-color:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.09);
                             border-radius:999px; padding:6px 14px;">
                    <span style="color:rgba(255,255,255,0.55); font-size:12px; font-weight:600;">
                      ⏱ Expira em {CODE_EXPIRATION_MINUTES} minutos
                    </span>
                  </td>
                </tr>
              </table>

              <!-- Aviso final -->
              <p style="color:rgba(255,255,255,0.38); font-size:12px; line-height:1.6; margin:10px 0 0 0; text-align:center;">
                Se você não solicitou essa redefinição, pode ignorar este e-mail com segurança —
                sua senha continuará a mesma.
              </p>
            </td>
          </tr>

          <!-- Rodapé -->
          <tr>
            <td style="padding:18px 32px; border-top:1px solid rgba(255,255,255,0.09);">
              <p style="color:rgba(255,255,255,0.38); font-size:11px; margin:0; text-align:center;">
                Painel Administrativo AAPM — SENAI Brás · e-mail automático, não responda.
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

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as servidor:
        servidor.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        servidor.sendmail(SMTP_EMAIL, [destinatario], msg.as_string())

    print("[DEBUG EMAIL] sendmail() concluído sem erros.")


def solicitar_reset_senha(db: Session, email: str) -> None:
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="E-mail não cadastrado no sistema.")

    if usuario.reset_code_expires_at and not usuario.reset_code_used:
        expira_em = usuario.reset_code_expires_at
        if expira_em.tzinfo is None:
            expira_em = expira_em.replace(tzinfo=timezone.utc)

        enviado_em = expira_em - timedelta(minutes=CODE_EXPIRATION_MINUTES)
        segundos_desde_envio = (datetime.now(timezone.utc) - enviado_em).total_seconds()

        if segundos_desde_envio < RESEND_COOLDOWN_SECONDS:
            restante = int(RESEND_COOLDOWN_SECONDS - segundos_desde_envio)
            raise HTTPException(
                status_code=429,
                detail={"message": f"Aguarde {restante} segundos para reenviar o código.", "retry_after": restante},
            )

    codigo = gerar_codigo_numerico()
    usuario.reset_code_hash = hash_codigo(codigo)
    usuario.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_EXPIRATION_MINUTES)
    usuario.reset_code_used = False

    db.add(usuario)
    db.commit()

    enviar_email_codigo(usuario.email, codigo, nome=usuario.nome)


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


# ─────────────────────────────────────────────────────────────────────────────
# ROTAS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    """
    Aceita JSON ou x-www-form-urlencoded, porque o login.html manda JSON
    primeiro ({email, senha, password}) e cai pra form-urlencoded
    ({username, password}) se receber 422.
    """
    content_type = request.headers.get("content-type", "")

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        email = form.get("username") or form.get("email")
        senha = form.get("password") or form.get("senha")
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="Corpo da requisição inválido.")
        email = body.get("email")
        senha = body.get("senha") or body.get("password")

    if not email or not senha:
        raise HTTPException(status_code=422, detail="E-mail e senha são obrigatórios.")

    credenciais = _Credenciais(email=email, senha=senha)
    return autenticar_usuario(db, credenciais)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(dados: RegistroRequest, db: Session = Depends(get_db)):
    return registrar_usuario(db, dados)


@router.post("/forgot-password")
async def forgot_password(dados: ForgotPasswordRequest, db: Session = Depends(get_db)):
    solicitar_reset_senha(db, dados.email)
    return {"message": "Código enviado com sucesso. Verifique seu e-mail."}


@router.post("/reset-password")
async def reset_password(dados: ResetPasswordRequest, db: Session = Depends(get_db)):
    redefinir_senha(db, dados.email, dados.code, dados.new_password)
    return {"message": "Senha redefinida com sucesso."}