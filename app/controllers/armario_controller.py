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

def atualizar(db: Session, armario_id: int, armario):
    db_armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not db_armario:
        return None
    dados = armario.model_dump() if hasattr(armario, "model_dump") else armario.dict()
    for key, value in dados.items():
        setattr(db_armario, key, value)
    db.commit()
    db.refresh(db_armario)
    return db_armario

def deletar(db: Session, armario_id: int):
    db_armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not db_armario:
        return False
    db.delete(db_armario)
    db.commit()
    return True