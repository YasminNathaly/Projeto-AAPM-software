from sqlalchemy.orm import Session

# Tenta importar da estrutura padrão (app.models.associado ou app.models)
try:
    from app.models.associado import Associado
except ModuleNotFoundError:
    from app.models import Associado


def criar(db: Session, associado):
    dados = associado.model_dump() if hasattr(associado, "model_dump") else associado.dict()
    db_associado = Associado(**dados)
    db.add(db_associado)
    db.commit()
    db.refresh(db_associado)
    return db_associado


def listar(db: Session):
    return db.query(Associado).all()


def obter_por_id(db: Session, associado_id: int):
    return db.query(Associado).filter(Associado.id == associado_id).first()


def atualizar(db: Session, associado_id: int, associado):
    db_associado = obter_por_id(db, associado_id)
    if not db_associado:
        return None

    dados_atualizados = (
        associado.model_dump(exclude_unset=True)
        if hasattr(associado, "model_dump")
        else associado.dict(exclude_unset=True)
    )

    for chave, valor in dados_atualizados.items():
        setattr(db_associado, chave, valor)

    db.commit()
    db.refresh(db_associado)
    return db_associado


def deletar(db: Session, associado_id: int):
    db_associado = obter_por_id(db, associado_id)
    if not db_associado:
        return False

    db.delete(db_associado)
    db.commit()
    return True