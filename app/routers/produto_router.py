from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.controllers import produto_controller
from app.database import get_db
from app.schemas.produto_schema import ProdutoCreate, ProdutoResponse

router = APIRouter(
    prefix="/produtos",
    tags=["Produtos"]
)

# 1. CADASTRAR UM NOVO PRODUTO
@router.post("/", response_model=ProdutoResponse, status_code=status.HTTP_201_CREATED)
def criar_produto(produto: ProdutoCreate, db: Session = Depends(get_db)):
    return produto_controller.criar_produto(db, produto)

# 2. LISTAR TODOS OS PRODUTOS
@router.get("/", response_model=List[ProdutoResponse])
def listar_produtos(db: Session = Depends(get_db)):
    return produto_controller.listar_produtos(db)

# 3. BUSCAR UM PRODUTO PELO ID
@router.get("/{produto_id}", response_model=ProdutoResponse)
def buscar_produto(produto_id: int, db: Session = Depends(get_db)):
    return produto_controller.buscar_produto_por_id(db, produto_id)

# 4. DELETAR UM PRODUTO
@router.delete("/{produto_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_produto(produto_id: int, db: Session = Depends(get_db)):
    return produto_controller.deletar_produto(db, produto_id)