from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base

class Associado(Base):
    __tablename__ = "associados"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    telefone = Column(String(20), nullable=True)
    endereco = Column(String(200), nullable=True)

    # Relacionamento para o FastAPI conseguir buscar as vendas do associado
    vendas = relationship("Venda", back_populates="associado", cascade="all, delete-orphan")