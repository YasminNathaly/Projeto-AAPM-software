from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    senha = Column(String(255), nullable=False)  # <--- Definido como 'senha'

    role = Column(String(20), default="FUNCIONARIO")
    ativo = Column(Boolean, default=True)

    # ── Recuperação de senha ("Esqueci minha senha") ──
    reset_code_hash = Column(String(64), nullable=True)
    reset_code_expires_at = Column(DateTime(timezone=True), nullable=True)
    reset_code_used = Column(Boolean, default=True)