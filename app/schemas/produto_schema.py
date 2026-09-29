from typing import Optional, List

from pydantic import BaseModel, field_validator


class VariacaoProdutoSchema(BaseModel):
    nome_variacao: str
    sku: Optional[str] = None
    estoque: Optional[int] = 0
    preco_adicional: Optional[float] = 0.0

    @field_validator("estoque", mode="before")
    def tratar_estoque_variacao(cls, v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    @field_validator("preco_adicional", mode="before")
    def tratar_preco_adicional(cls, v):
        try:
            return float(v or 0.0)
        except (TypeError, ValueError):
            return 0.0


# O que a API espera RECEBER ao cadastrar/editar um produto
class ProdutoCreate(BaseModel):
    nome: str
    categoria_id: Optional[int] = None
    categoria: Optional[str] = None
    cor: Optional[str] = None
    tamanho: Optional[str] = ""
    preco: float
    quantidade: Optional[int] = 0
    estoque: Optional[int] = 0
    disponivel: Optional[bool] = True
    imagem_url: Optional[str] = ""
    variacoes: Optional[List[VariacaoProdutoSchema]] = []

    @field_validator("categoria_id", mode="before")
    def tratar_categoria(cls, v):
        if v in (None, "", "null"):
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    @field_validator("quantidade", mode="before")
    def tratar_quantidade(cls, v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    @field_validator("estoque", mode="before")
    def tratar_estoque(cls, v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    @field_validator("preco", mode="before")
    def tratar_preco(cls, v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0


# O que a API vai DEVOLVER (inclui o ID do banco)
class ProdutoResponse(BaseModel):
    id: int
    nome: str
    categoria_id: Optional[int] = None
    categoria: Optional[str] = None
    cor: Optional[str] = None
    tamanho: Optional[str] = ""
    preco: float
    quantidade: Optional[int] = 0
    estoque: Optional[int] = 0
    disponivel: Optional[bool] = True
    imagem_url: Optional[str] = ""
    variacoes: Optional[List[VariacaoProdutoSchema]] = []

    class Config:
        from_attributes = True