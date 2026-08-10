from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    cor = Column(String(30), nullable=True)
    tamanho = Column(String(20), nullable=True)
    preco = Column(Float, nullable=False)
    estoque = Column(Integer, default=0)
    disponivel = Column(Boolean, default=True)
    imagem_url = Column(String(255), nullable=True, default="")
    
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    categoria = relationship("Categoria", back_populates="produtos")
