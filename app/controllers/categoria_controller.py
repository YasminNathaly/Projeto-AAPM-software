from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.categoria import Categoria


def listar_categorias(db: Session):
    return db.query(Categoria).order_by(Categoria.id.asc()).all()


def criar_categoria(db: Session, categoria_data):
    categoria = db.query(Categoria).filter(Categoria.nome == categoria_data.nome).first()
    if categoria:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Categoria já cadastrada",
        )

    nova_categoria = Categoria(nome=categoria_data.nome)
    db.add(nova_categoria)
    db.commit()
    db.refresh(nova_categoria)
    return nova_categoria


def buscar_categoria_por_id(db: Session, categoria_id: int):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada",
        )
    return categoria


def deletar_categoria(db: Session, categoria_id: int):
    categoria = buscar_categoria_por_id(db, categoria_id)
    db.delete(categoria)
    db.commit()
    return None
