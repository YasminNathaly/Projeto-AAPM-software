from sqlalchemy.orm import Session
from app.models.armario import Armario

def listar(db: Session):
    return db.query(Armario).all()

def criar(db: Session, armario):
    dados = armario.model_dump() if hasattr(armario, "model_dump") else armario.dict()
    db_armario = Armario(**dados)
    db.add(db_armario)
    db.commit()
    db.refresh(db_armario)
    return db_armario

def reservar(db: Session, armario_id: int, nome_completo: str):
    db_armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not db_armario:
        return None

    db_armario.status = "Ocupado"
    db_armario.nome_completo = nome_completo

    db.commit()
    db.refresh(db_armario)
    return db_armario

def liberar(db: Session, armario_id: int):
    db_armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not db_armario:
        return None

    db_armario.status = "Disponível"
    db_armario.nome_completo = None

    db.commit()
    db.refresh(db_armario)
    return db_armario