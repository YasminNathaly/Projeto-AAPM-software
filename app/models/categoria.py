from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base

class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)

    # Relacionamento para o FastAPI conseguir buscar os produtos da categoria
    produtos = relationship("Produto", back_populates="categoria", cascade="all, delete-orphan")