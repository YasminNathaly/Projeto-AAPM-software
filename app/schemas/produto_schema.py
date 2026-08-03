from pydantic import BaseModel

# O que a API espera RECEBER ao cadastrar/editar um produto
class ProdutoCreate(BaseModel):
    nome: str
    categoria: str
    cor: str
    tamanho: str
    preco: float
    estoque: int = 0

# O que a API vai DEVOLVER (inclui o ID do banco)
class ProdutoResponse(ProdutoCreate):
    id: int

    class Config:
        from_attributes = True