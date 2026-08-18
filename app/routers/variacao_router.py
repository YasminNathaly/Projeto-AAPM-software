from typing import List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.controllers import variacao_controller
from app.database import get_db


class VariacaoCreate(BaseModel):
    nome_variacao: str
    sku: Optional[str] = None
    estoque: int = 0
    preco_adicional: float = 0.0


class VariacaoResponse(BaseModel):
    id: int
    produto_id: int
    nome_variacao: str
    sku: Optional[str] = None
    estoque: int = 0
    preco_adicional: float = 0.0

    class Config:
        from_attributes = True


router = APIRouter(prefix="/produtos", tags=["Variações"])


@router.get("/{produto_id}/variacoes", response_model=List[VariacaoResponse])
def listar_variacoes(produto_id: int, db: Session = Depends(get_db)):
    return variacao_controller.listar_variacoes(db, produto_id=produto_id)


@router.post("/{produto_id}/variacoes", response_model=VariacaoResponse, status_code=status.HTTP_201_CREATED)
def criar_variacao(produto_id: int, dados: VariacaoCreate, db: Session = Depends(get_db)):
    return variacao_controller.criar_variacao(db, produto_id, dados)


@router.put("/variacoes/{variacao_id}", response_model=VariacaoResponse)
def atualizar_variacao(variacao_id: int, dados: VariacaoCreate, db: Session = Depends(get_db)):
    return variacao_controller.atualizar_variacao(db, variacao_id, dados)


@router.delete("/variacoes/{variacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_variacao(variacao_id: int, db: Session = Depends(get_db)):
    return variacao_controller.deletar_variacao(db, variacao_id)
