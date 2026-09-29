from sqlalchemy.orm import Session

# Tenta importar da estrutura padrão (app.models.associado ou app.models)
try:
    from app.models.associado import Associado
except ModuleNotFoundError:
    from app.models import Associado

def _normalizar_status(dados):
    status = getattr(dados, "status", None)
    if status is None or str(status).strip() == "":
        status = "Ativo"
    status_norm = str(status).strip().title()
    if status_norm not in {"Ativo", "Inativo"}:
        status_norm = "Ativo"
    return status_norm


def _normalizar_ativo(dados):
    ativo = getattr(dados, "ativo", None)
    if ativo is None:
        return True
    if isinstance(ativo, bool):
        return ativo
    if isinstance(ativo, str):
        return ativo.strip().lower() in {"true", "1", "ativo", "yes", "on"}
    return bool(ativo)


def criar(db: Session, associado):
    dados = associado.model_dump() if hasattr(associado, "model_dump") else associado.dict()

    dados["status"] = _normalizar_status(associado)
    dados["ativo"] = _normalizar_ativo(associado)

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

    if "status" in dados_atualizados:
        dados_atualizados["status"] = _normalizar_status(type("S", (), dados_atualizados)())
    else:
        dados_atualizados["status"] = "Ativo"

    if "ativo" in dados_atualizados:
        dados_atualizados["ativo"] = _normalizar_ativo(type("S", (), dados_atualizados)())
    else:
        dados_atualizados["ativo"] = True

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