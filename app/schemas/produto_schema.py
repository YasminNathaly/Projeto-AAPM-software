from typing import List, Optional
from pydantic import BaseModel

class VariacaoItem(BaseModel):
    id: Optional[int] = None
    nome_variacao: str
    estoque: int = 0
    preco_adicional: float = 0.0

    class Config:
        from_attributes = True

class ProdutoCreate(BaseModel):
    nome: str
    categoria: Optional[str] = None
    categoria_id: Optional[int] = None
    cor: Optional[str] = ""
    tamanho: Optional[str] = ""
    preco: float
    estoque: int = 0
    quantidade: Optional[int] = None
    imagem_url: Optional[str] = ""
    disponivel: Optional[bool] = True
    variacoes: Optional[List[VariacaoItem]] = []

class ProdutoResponse(ProdutoCreate):
    id: int

    class Config:
        from_attributes = True
