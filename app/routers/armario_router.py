from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.controllers import armario_controller

router = APIRouter(prefix="/api/armarios", tags=["Armários"])


class ArmarioBase(BaseModel):
    numero: str
    localizacao: Optional[str] = None
    status: Optional[str] = "Disponível"
    nome_completo: Optional[str] = None
    curso: Optional[str] = None


class ArmarioCreate(ArmarioBase):
    pass


class ArmarioUpdate(ArmarioBase):
    pass


class ArmarioResponse(ArmarioBase):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ArmarioResponse])
def listar(db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        db.execute(text("ALTER TABLE armarios ADD COLUMN updated_at TIMESTAMP"))
        db.commit()
    except Exception:
        db.rollback()
    try:
        db.execute(text("ALTER TABLE armarios ADD COLUMN curso VARCHAR"))
        db.commit()
    except Exception:
        db.rollback()
    itens = armario_controller.listar(db)
    import re
    alterou = False
    for item in itens:
        if item.nome_completo:
            txt_nc = item.nome_completo.split("\u2022")[0].split("?")[0].strip()
            m_curso = re.match(r"^(.*?)\s*\(([^()]+)\)$", txt_nc)
            if m_curso and not item.curso:
                item.nome_completo = m_curso.group(1).strip()
                item.curso = m_curso.group(2).strip()
                alterou = True
            elif txt_nc != item.nome_completo:
                item.nome_completo = txt_nc
                alterou = True
    if alterou:
        db.commit()
    return sorted(itens, key=lambda x: (x.updated_at or datetime.min, x.id), reverse=True)


@router.post("/", response_model=ArmarioResponse, status_code=status.HTTP_201_CREATED)
def criar(armario: ArmarioCreate, db: Session = Depends(get_db)):
    return armario_controller.criar(db, armario)


@router.put("/{armario_id}", response_model=ArmarioResponse)
def atualizar(armario_id: int, armario: ArmarioUpdate, db: Session = Depends(get_db)):
    res = armario_controller.atualizar(db, armario_id, armario)
    if not res:
        raise HTTPException(status_code=404, detail="Armário não encontrado.")
    return res


@router.delete("/{armario_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar(armario_id: int, db: Session = Depends(get_db)):
    sucesso = armario_controller.deletar(db, armario_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Armário não encontrado.")
    return None

class ReservaPublicaRequest(BaseModel):
    armario_id: int
    nome: str
    turma: str
    telefone: Optional[str] = None


@router.post("/reservar-publico", response_model=ArmarioResponse)
def reservar_publico(dados: ReservaPublicaRequest, db: Session = Depends(get_db)):
    from app.models.armario import Armario
    from datetime import datetime, timedelta
    db_armario = db.query(Armario).filter(Armario.id == dados.armario_id).first()
    if not db_armario:
        raise HTTPException(status_code=404, detail="Arm\u00e1rio n\u00e3o encontrado.")
    status_atual = (db_armario.status or "").strip().lower()
    if not status_atual.startswith("dispon") and status_atual != "livre":
        raise HTTPException(
            status_code=400,
            detail=f"Este arm\u00e1rio n\u00e3o est\u00e1 dispon\u00edvel (status atual: {db_armario.status})."
        )
    validade = (datetime.now() + timedelta(hours=24)).strftime("%d/%m %H:%M")
    nome_limpo = dados.nome.strip()
    turma_limpa = dados.turma.strip()
        db_armario.status = "Ocupado"
    db_armario.updated_at = datetime.now()
    db_armario.nome_completo = nome_limpo
    db_armario.curso = turma_limpa
    db.commit()
    db.refresh(db_armario)
    return db_armario
