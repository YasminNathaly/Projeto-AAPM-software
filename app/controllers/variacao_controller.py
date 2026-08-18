from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.models.variacao import VariacaoProduto


def listar_variacoes(db: Session, produto_id: int | None = None):
    query = db.query(VariacaoProduto)
    if produto_id is not None:
        query = query.filter(VariacaoProduto.produto_id == produto_id)
    return query.order_by(VariacaoProduto.id.asc()).all()


def buscar_variacao(db: Session, variacao_id: int):
    variacao = db.query(VariacaoProduto).filter(VariacaoProduto.id == variacao_id).first()
    if not variacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variação não encontrada",
        )
    return variacao


def criar_variacao(db: Session, produto_id: int, dados):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado para associar a variação",
        )

    nome_variacao = getattr(dados, "nome_variacao", None) or getattr(dados, "nome", None)
    if not nome_variacao:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome da variação é obrigatório",
        )

    nova_variacao = VariacaoProduto(
        produto_id=produto_id,
        nome_variacao=nome_variacao,
        sku=getattr(dados, "sku", None),
        estoque=getattr(dados, "estoque", 0) or 0,
        preco_adicional=float(getattr(dados, "preco_adicional", 0.0) or 0.0),
    )

    db.add(nova_variacao)
    db.commit()
    db.refresh(nova_variacao)
    return nova_variacao


def atualizar_variacao(db: Session, variacao_id: int, dados):
    variacao = buscar_variacao(db, variacao_id)

    if hasattr(dados, "nome_variacao") and dados.nome_variacao:
        variacao.nome_variacao = dados.nome_variacao
    elif isinstance(dados, dict) and dados.get("nome_variacao"):
        variacao.nome_variacao = dados.get("nome_variacao")

    if hasattr(dados, "sku"):
        variacao.sku = dados.sku
    elif isinstance(dados, dict) and "sku" in dados:
        variacao.sku = dados.get("sku")

    if hasattr(dados, "estoque"):
        variacao.estoque = int(dados.estoque or 0)
    elif isinstance(dados, dict) and "estoque" in dados:
        variacao.estoque = int(dados.get("estoque") or 0)

    if hasattr(dados, "preco_adicional"):
        variacao.preco_adicional = float(dados.preco_adicional or 0.0)
    elif isinstance(dados, dict) and "preco_adicional" in dados:
        variacao.preco_adicional = float(dados.get("preco_adicional") or 0.0)

    db.commit()
    db.refresh(variacao)
    return variacao


def deletar_variacao(db: Session, variacao_id: int):
    variacao = buscar_variacao(db, variacao_id)
    db.delete(variacao)
    db.commit()
    return None
