import math
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.produto import Produto, buscar_produtos_paginado
from app.schemas.produto_schema import ProdutoCreate


def listar_produtos(db: Session, pagina: int = 1, limite: int = 10):
    # Chama a função paginada do model
    itens, total = buscar_produtos_paginado(db, pagina=pagina, limite=limite)

    # Calcula o total de páginas
    total_paginas = math.ceil(total / limite) if total > 0 else 1

    return {
        "produtos": itens,
        "total_itens": total,
        "pagina_atual": pagina,
        "total_paginas": total_paginas,
    }


def criar_produto(db: Session, produto_data: ProdutoCreate):
    novo_produto = Produto(**produto_data.model_dump())
    db.add(novo_produto)
    db.commit()
    db.refresh(novo_produto)
    return novo_produto


def buscar_produto_por_id(db: Session, produto_id: int):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado",
        )
    return produto


def deletar_produto(db: Session, produto_id: int):
    produto = buscar_produto_por_id(db, produto_id)
    db.delete(produto)
    db.commit()
    return None