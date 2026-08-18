from typing import List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.controllers import fornecedor_controller
from app.database import get_db


class FornecedorCreate(BaseModel):
    nome: str
    cnpj: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None


class FornecedorResponse(BaseModel):
    id: int
    nome: str
    cnpj: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


router = APIRouter(prefix="/fornecedores", tags=["Fornecedores"])


@router.get("/", response_model=List[FornecedorResponse])
def listar_fornecedores(db: Session = Depends(get_db)):
    return fornecedor_controller.listar_fornecedores(db)


@router.post("/", response_model=FornecedorResponse, status_code=status.HTTP_201_CREATED)
def criar_fornecedor(fornecedor: FornecedorCreate, db: Session = Depends(get_db)):
    return fornecedor_controller.criar_fornecedor(db, fornecedor)


@router.get("/{fornecedor_id}", response_model=FornecedorResponse)
def buscar_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    return fornecedor_controller.buscar_fornecedor_por_id(db, fornecedor_id)


@router.delete("/{fornecedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_fornecedor(fornecedor_id: int, db: Session = Depends(get_db)):
    return fornecedor_controller.deletar_fornecedor(db, fornecedor_id)
