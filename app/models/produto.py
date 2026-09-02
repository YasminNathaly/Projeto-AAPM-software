from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship, Session
from app.database import Base
from app.models.variacao import VariacaoProduto  # <-- Ajuste o caminho se o nome do arquivo for diferente


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    cor = Column(String(30), nullable=True)
    tamanho = Column(String(20), nullable=True)
    preco = Column(Float, nullable=False)
    estoque = Column(Integer, default=0)
    disponivel = Column(Boolean, default=True)

    # Removido 'primary_key=True' para não conflitar com o id
    quantidade = Column(Integer, default=0, nullable=True)

    imagem_url = Column(String(255), nullable=True, default="")

    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    categoria = relationship("Categoria", back_populates="produtos")

    # Movidas para DENTRO da classe (indentadas)
    variacoes = relationship("VariacaoProduto", back_populates="produto", cascade="all, delete-orphan")


# ==========================================
# FUNÇÃO DE PAGINAÇÃO (Fora da classe)
# ==========================================
def buscar_produtos_paginado(db: Session, pagina: int = 1, limite: int = 12):
    offset = (pagina - 1) * limite
    total = db.query(Produto).count()
    itens = db.query(Produto).order_by(Produto.id.desc()).offset(offset).limit(limite).all()
    return itens, total