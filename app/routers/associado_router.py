from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.controllers import associado_controller
from app.database import get_db

# Prefixo configurado para casar com as chamadas /api/associados do front-end
router = APIRouter(prefix="/api/associados", tags=["Associados"])


# --- Schemas (Pydantic) ---
class AssociadoBase(BaseModel):
    nome: str
    email: str
    telefone: Optional[str] = None
    endereco: Optional[str] = None


class AssociadoCreate(AssociadoBase):
    pass


class AssociadoUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[str] = None
    telefone: Optional[str] = None
    endereco: Optional[str] = None


class AssociadoResponse(AssociadoBase):
    id: int

    class Config:
        from_attributes = True  # Pydantic v2 (use orm_mode = True se estiver no Pydantic v1)


# --- Endpoints ---

@router.post("/", response_model=AssociadoResponse, status_code=status.HTTP_201_CREATED)
def criar(associado: AssociadoCreate, db: Session = Depends(get_db)):
    return associado_controller.criar(db=db, associado=associado)


@router.get("/", response_model=List[AssociadoResponse])
def listar(db: Session = Depends(get_db)):
    return associado_controller.listar(db=db)


@router.get("/{associado_id}", response_model=AssociadoResponse)
def buscar_por_id(associado_id: int, db: Session = Depends(get_db)):
    db_associado = associado_controller.obter_por_id(db=db, associado_id=associado_id)
    if not db_associado:
        raise HTTPException(status_code=404, detail="Associado não encontrado.")
    return db_associado


@router.put("/{associado_id}", response_model=AssociadoResponse)
def atualizar(associado_id: int, associado: AssociadoUpdate, db: Session = Depends(get_db)):
    db_associado = associado_controller.atualizar(db=db, associado_id=associado_id, associado=associado)
    if not db_associado:
        raise HTTPException(status_code=404, detail="Associado não encontrado.")
    return db_associado


@router.delete("/{associado_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(associado_id: int, db: Session = Depends(get_db)):
    sucesso = associado_controller.deletar(db=db, associado_id=associado_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Associado não encontrado.")
    return None