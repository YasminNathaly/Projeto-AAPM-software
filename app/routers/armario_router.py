from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.controllers import armario_controller

router = APIRouter(prefix="/api/armarios", tags=["Armários"])


# --- Schemas Pydantic ---
class ArmarioBase(BaseModel):
    numero: str
    localizacao: Optional[str] = None
    status: Optional[str] = "Disponível"
    nome_completo: Optional[str] = None


class ArmarioCreate(ArmarioBase):
    pass


class ArmarioResponse(ArmarioBase):
    id: int

    class Config:
        from_attributes = True


# --- Endpoints ---
@router.get("/", response_model=List[ArmarioResponse])
def listar(db: Session = Depends(get_db)):
    return armario_controller.listar(db)


@router.post("/", response_model=ArmarioResponse, status_code=status.HTTP_201_CREATED)
def criar(armario: ArmarioCreate, db: Session = Depends(get_db)):
    return armario_controller.criar(db, armario)


@router.put("/{armario_id}/liberar", response_model=ArmarioResponse)
def liberar(armario_id: int, db: Session = Depends(get_db)):
    res = armario_controller.liberar(db, armario_id)
    if not res:
        raise HTTPException(status_code=404, detail="Armário não encontrado.")
    return res