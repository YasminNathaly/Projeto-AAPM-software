import math
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.produto import Produto
from app.models.variacao import VariacaoProduto
from app.models.categoria import Categoria
from app.schemas.produto_schema import ProdutoCreate


def _serializar_produto(p: Produto):
    return {
        "id": p.id,
        "nome": p.nome,
        "cor": p.cor or "",
        "tamanho": p.tamanho or "",
        "preco": float(p.preco or 0),
        "estoque": int(p.estoque or 0),
        "quantidade": int(p.quantidade if p.quantidade is not None else (p.estoque or 0)),
        "disponivel": bool(p.disponivel if p.disponivel is not None else True),
        "imagem_url": p.imagem_url or "",
        "categoria_id": p.categoria_id,
        "categoria": p.categoria.nome if p.categoria else "",
        "variacoes": [
            {
                "id": v.id,
                "nome_variacao": v.nome_variacao,
                "estoque": int(v.estoque or 0),
                "preco_adicional": float(v.preco_adicional or 0.0),
            }
            for v in (p.variacoes or [])
        ],
    }


def listar_produtos(db: Session, pagina: int = 1, limite: int = 100):
    offset = (pagina - 1) * limite
    total = db.query(Produto).count()
    itens = (
        db.query(Produto)
        .options(joinedload(Produto.variacoes), joinedload(Produto.categoria))
        .order_by(Produto.id.desc())
        .offset(offset)
        .limit(limite)
        .all()
    )
    total_paginas = math.ceil(total / limite) if total > 0 else 1
    return {
        "produtos": [_serializar_produto(p) for p in itens],
        "total_itens": total,
        "pagina_atual": pagina,
        "total_paginas": total_paginas,
    }


def _resolver_categoria_id(db: Session, produto_data: ProdutoCreate):
    if produto_data.categoria_id:
        return produto_data.categoria_id
    if produto_data.categoria:
        cat = db.query(Categoria).filter(Categoria.nome.ilike(produto_data.categoria.strip())).first()
        if cat:
            return cat.id
    return None


def _sincronizar_variacoes(db: Session, produto: Produto, variacoes_in):
    produto.variacoes.clear()
    db.flush()
    if variacoes_in:
        for v in variacoes_in:
            nome_v = (v.nome_variacao or "").strip()
            if nome_v:
                produto.variacoes.append(
                    VariacaoProduto(
                        nome_variacao=nome_v,
                        estoque=int(v.estoque or 0),
                        preco_adicional=float(v.preco_adicional or 0.0),
                    )
                )


def criar_produto(db: Session, produto_data: ProdutoCreate):
    cat_id = _resolver_categoria_id(db, produto_data)
    qtd = produto_data.quantidade if produto_data.quantidade is not None else produto_data.estoque
    novo_produto = Produto(
        nome=produto_data.nome,
        cor=produto_data.cor or "",
        tamanho=produto_data.tamanho or "",
        preco=produto_data.preco,
        estoque=int(qtd or 0),
        quantidade=int(qtd or 0),
        disponivel=True if produto_data.disponivel is None else produto_data.disponivel,
        imagem_url=produto_data.imagem_url or "",
        categoria_id=cat_id,
    )
    db.add(novo_produto)
    db.flush()
    _sincronizar_variacoes(db, novo_produto, produto_data.variacoes)
    db.commit()
    db.refresh(novo_produto)
    return _serializar_produto(novo_produto)


def atualizar_produto(db: Session, produto_id: int, produto_data: ProdutoCreate):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto n?o encontrado")
    cat_id = _resolver_categoria_id(db, produto_data)
    qtd = produto_data.quantidade if produto_data.quantidade is not None else produto_data.estoque
    produto.nome = produto_data.nome
    produto.cor = produto_data.cor or ""
    produto.tamanho = produto_data.tamanho or ""
    produto.preco = produto_data.preco
    produto.estoque = int(qtd or 0)
    produto.quantidade = int(qtd or 0)
    if produto_data.disponivel is not None:
        produto.disponivel = produto_data.disponivel
    if produto_data.imagem_url is not None:
        produto.imagem_url = produto_data.imagem_url
    if cat_id is not None:
        produto.categoria_id = cat_id
    _sincronizar_variacoes(db, produto, produto_data.variacoes)
    db.commit()
    db.refresh(produto)
    return _serializar_produto(produto)


def buscar_produto_por_id(db: Session, produto_id: int):
    produto = (
        db.query(Produto)
        .options(joinedload(Produto.variacoes), joinedload(Produto.categoria))
        .filter(Produto.id == produto_id)
        .first()
    )
    if not produto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto n?o encontrado")
    return _serializar_produto(produto)


def deletar_produto(db: Session, produto_id: int):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto n?o encontrado")
    db.delete(produto)
    db.commit()
    return None
