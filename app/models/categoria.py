from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base

class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    codigo = Column(String, nullable=True)  # <-- ADICIONE ESTA LINHA
    descricao = Column(String, nullable=True)

    produtos = relationship("Produto", back_populates="categoria")