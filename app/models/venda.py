from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Venda(Base):
    __tablename__ = "vendas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True) # Pode ser nulo para venda no balcão sem cadastro
    valor_total = Column(Float, nullable=False)
    status = Column(String(30), default="Concluída") # ex: "Pendente", "Concluída", "Cancelada"
    data_venda = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamento com os itens da venda
    itens = relationship("ItemVenda", back_populates="venda", cascade="all, delete-orphan")


class ItemVenda(Base):
    __tablename__ = "itens_venda"

    id = Column(Integer, primary_key=True, index=True)
    venda_id = Column(Integer, ForeignKey("vendas.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, nullable=False, default=1)
    preco_unitario = Column(Float, nullable=False) # Guarda o preço do produto no momento exato da compra

    # Relacionamentos
    venda = relationship("Venda", back_populates="itens")
    produto = relationship("Produto")