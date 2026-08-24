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

def reservar(db: Session, armario_id: int, dados_reserva):
    db_armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not db_armario:
        return None

    db_armario.status = "RESERVADO"
    db_armario.nome = dados_reserva.nome
    db_armario.matricula = dados_reserva.matricula
    db_armario.cpf = dados_reserva.cpf

    db.commit()
    db.refresh(db_armario)
    return db_armario

def liberar(db: Session, armario_id: int):
    db_armario = db.query(Armario).filter(Armario.id == armario_id).first()
    if not db_armario:
        return None

    db_armario.status = "LIVRE"
    db_armario.nome = None
    db_armario.matricula = None
    db_armario.cpf = None

    db.commit()
    db.refresh(db_armario)
    return db_armario