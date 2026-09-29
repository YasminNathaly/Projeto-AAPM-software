import math
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.produto import Produto, buscar_produtos_paginado
from app.models.variacao import VariacaoProduto
from app.schemas.produto_schema import ProdutoCreate


def _extrair_variacao(item):
    if isinstance(item, dict):
        nome = item.get("nome_variacao") or item.get("nome") or item.get("name") or ""
        return {
            "nome_variacao": str(nome).strip(),
            "sku": item.get("sku"),
            "estoque": item.get("estoque") if item.get("estoque") is not None else item.get("quantidade", 0),
            "preco_adicional": item.get("preco_adicional", 0.0),
        }

    nome = getattr(item, "nome_variacao", None) or getattr(item, "nome", None) or getattr(item, "name", None) or ""
    return {
        "nome_variacao": str(nome).strip(),
        "sku": getattr(item, "sku", None),
        "estoque": getattr(item, "estoque", getattr(item, "quantidade", 0)) or 0,
        "preco_adicional": getattr(item, "preco_adicional", 0.0) or 0.0,
    }


def _sincronizar_variacoes_produto(db: Session, produto: Produto, variacoes_payload):
    if VariacaoProduto is None:
        return

    for variacao_atual in list(getattr(produto, "variacoes", []) or []):
        db.delete(variacao_atual)

    db.flush()

    for item in variacoes_payload or []:
        dados_variacao = _extrair_variacao(item)
        if not dados_variacao["nome_variacao"]:
            continue

        produto_variacao = VariacaoProduto(
            produto_id=produto.id,
            nome_variacao=dados_variacao["nome_variacao"],
            sku=dados_variacao["sku"],
            estoque=int(dados_variacao["estoque"] or 0),
            preco_adicional=float(dados_variacao["preco_adicional"] or 0.0),
        )
        db.add(produto_variacao)

    if variacoes_payload:
        total_estoque_variacoes = sum(int(_extrair_variacao(item).get("estoque") or 0) for item in variacoes_payload)
        produto.quantidade = total_estoque_variacoes
        produto.estoque = total_estoque_variacoes

    db.commit()
    db.refresh(produto)


def listar_produtos(db: Session, pagina: int = 1, limite: int = 10):
    itens, total = buscar_produtos_paginado(db, pagina=pagina, limite=limite)
    total_paginas = math.ceil(total / limite) if total > 0 else 1
    return {
        "produtos": itens,
        "total_itens": total,
        "pagina_atual": pagina,
        "total_paginas": total_paginas,
    }


def criar_produto(db: Session, produto_data: ProdutoCreate):
    novo_produto = Produto(**produto_data.model_dump(exclude={"variacoes"}))
    db.add(novo_produto)
    db.commit()
    db.refresh(novo_produto)

    _sincronizar_variacoes_produto(db, novo_produto, getattr(produto_data, "variacoes", []) or [])
    return novo_produto


def buscar_produto_por_id(db: Session, produto_id: int):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado",
        )
    return produto


def atualizar_produto(db: Session, produto_id: int, produto_data: ProdutoCreate):
    produto = buscar_produto_por_id(db, produto_id)
    payload = produto_data.model_dump(exclude={"variacoes"})
    for key, value in payload.items():
        setattr(produto, key, value)

    db.commit()
    db.refresh(produto)
    _sincronizar_variacoes_produto(db, produto, getattr(produto_data, "variacoes", []) or [])
    return produto


def deletar_produto(db: Session, produto_id: int):
    produto = buscar_produto_por_id(db, produto_id)
    db.delete(produto)
    db.commit()
    return None