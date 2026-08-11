# app/models/variacao.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class VariacaoProduto(Base):
    __tablename__ = "variacoes_produto"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    
    # Ex: Tamanho (P, M, G, 42), Cor (Azul, Preto) ou Atributo do Retoque
    nome_variacao = Column(String(50), nullable=False)  # Ex: "Tamanho M", "Retoque Padrão"
    sku = Column(String(50), unique=True, nullable=True)
    estoque = Column(Integer, default=0)
    preco_adicional = Column(Float, default=0.0)  # Caso alguma variação/retoque mude o preço base

    produto = relationship("Produto", back_populates="variacoes")