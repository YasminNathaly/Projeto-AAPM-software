from sqlalchemy import Column, Integer, String
from app.database import Base

class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    documento = Column(String)  # <-- Adicione este campo se estiver faltando
    email = Column(String)
    telefone = Column(String)