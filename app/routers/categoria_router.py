from typing import List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.controllers import categoria_controller
from app.database import get_db


class CategoriaCreate(BaseModel):
    nome: str
    codigo: Optional[str] = ""
    descricao: Optional[str] = ""


class CategoriaResponse(BaseModel):
    id: int
    nome: str
    codigo: Optional[str] = ""
    descricao: Optional[str] = ""

    class Config:
        from_attributes = True


# Ajustado o prefixo para coincidir com a API
router = APIRouter(prefix="/api/categorias", tags=["Categorias"])


@router.get("/", response_model=List[CategoriaResponse])
def listar_categorias(db: Session = Depends(get_db)):
    return categoria_controller.listar_categorias(db)


@router.post("/", response_model=CategoriaResponse, status_code=status.HTTP_201_CREATED)
def criar_categoria(categoria: CategoriaCreate, db: Session = Depends(get_db)):
    return categoria_controller.criar_categoria(db, categoria)


@router.put("/{categoria_id}", response_model=CategoriaResponse)
def atualizar_categoria(categoria_id: int, categoria: CategoriaCreate, db: Session = Depends(get_db)):
    return categoria_controller.atualizar_categoria(db, categoria_id, categoria)


@router.get("/{categoria_id}", response_model=CategoriaResponse)
def buscar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    return categoria_controller.buscar_categoria_por_id(db, categoria_id)


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    return categoria_controller.deletar_categoria(db, categoria_id)