from sqlalchemy import Column, Integer, String
from app.database import Base

class Fornecedor(Base):
    __tablename__ = "fornecedores"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    cnpj = Column(String(20), nullable=True, unique=True)
    telefone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)