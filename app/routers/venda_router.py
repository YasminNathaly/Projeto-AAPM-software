from typing import List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.controllers import venda_controller
from app.database import get_db


class ItemVendaInput(BaseModel):
    produto_id: int
    quantidade: int = 1
    preco_unitario: Optional[float] = 0.0


class VendaCreate(BaseModel):
    cliente: Optional[str] = "Cliente Não Informado"
    comprador: Optional[str] = None
    produto_id: Optional[int] = None
    quantidade: int = 1
    preco_total: Optional[float] = 0.0
    valor_total: Optional[float] = None
    forma_pagamento: str = "PIX"
    status: str = "Concluída"
    itens: Optional[List[ItemVendaInput]] = None


class VendaResponse(BaseModel):
    id: int
    cliente: Optional[str] = "Cliente Não Informado"
    comprador: Optional[str] = "Cliente Não Informado"
    produto_id: Optional[int] = None
    quantidade: int = 1
    preco_total: float = 0.0
    valor_total: Optional[float] = 0.0
    forma_pagamento: str = "PIX"
    status: str = "Concluída"
    data_venda: Optional[str] = None
    itens: List[dict] = []


router = APIRouter(prefix="/api/vendas", tags=["Vendas"])


@router.get("/", response_model=List[VendaResponse])
@router.get("", response_model=List[VendaResponse])
async def listar_vendas(db: Session = Depends(get_db)):
    return venda_controller.listar_vendas(db)


@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def registrar_venda(dados: VendaCreate, db: Session = Depends(get_db)):
    return venda_controller.registrar_venda(db, dados)