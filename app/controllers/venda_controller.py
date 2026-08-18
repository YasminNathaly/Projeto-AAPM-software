from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.produto import Produto
from app.models.variacao import VariacaoProduto
from app.models.venda import ItemVenda, Venda


def _formatar_data_venda(valor):
    if valor is None:
        return None
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)


def _normalizar_cliente(dados):
    if hasattr(dados, "model_dump"):
        payload = dados.model_dump()
    elif isinstance(dados, dict):
        payload = dados
    else:
        payload = {}

    cliente = (
        payload.get("cliente")
        or payload.get("comprador")
        or payload.get("nome_cliente")
        or "Cliente Não Informado"
    )
    return str(cliente).strip() or "Cliente Não Informado"


def _normalizar_itens(dados):
    if hasattr(dados, "model_dump"):
        payload = dados.model_dump()
    elif isinstance(dados, dict):
        payload = dados
    else:
        payload = {}

    itens = payload.get("itens")
    if itens:
        return itens

    produto_id = payload.get("produto_id")
    quantidade = payload.get("quantidade") or 1
    if produto_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="É necessário informar o produto da venda",
        )

    return [{
        "produto_id": produto_id,
        "variacao_id": payload.get("variacao_id"),
        "quantidade": quantidade,
        "preco_unitario": payload.get("preco_unitario") or 0.0,
    }]


def listar_vendas(db: Session):
    vendas = db.query(Venda).order_by(Venda.id.desc()).all()
    resposta = []
    for venda in vendas:
        itens = []
        for item in getattr(venda, "itens", []) or []:
            nome_produto = "Produto indisponível"
            produto = db.query(Produto).filter(Produto.id == item.produto_id).first()
            if produto:
                nome_produto = produto.nome

            nome_variacao = ""
            if getattr(item, "variacao_id", None):
                variacao = db.query(VariacaoProduto).filter(VariacaoProduto.id == item.variacao_id).first()
                if variacao:
                    nome_variacao = variacao.nome_variacao

            itens.append(
                {
                    "id": item.id,
                    "produto_id": item.produto_id,
                    "variacao_id": item.variacao_id,
                    "variacao_nome": nome_variacao,
                    "produto_nome": nome_produto,
                    "quantidade": item.quantidade,
                    "preco_unitario": item.preco_unitario,
                }
            )

        cliente_nome = getattr(venda, "cliente", None) or getattr(venda, "comprador", None) or "Cliente Não Informado"
        resposta.append(
            {
                "id": venda.id,
                "cliente": cliente_nome,
                "comprador": cliente_nome,
                "produto_id": getattr(venda, "produto_id", None),
                "produto_nome": itens[0]["produto_nome"] if itens else "Produto não informado",
                "quantidade": getattr(venda, "quantidade", itens[0]["quantidade"] if itens else 1),
                "valor_total": getattr(venda, "valor_total", getattr(venda, "preco_total", 0.0)),
                "preco_total": getattr(venda, "preco_total", getattr(venda, "valor_total", 0.0)),
                "status": getattr(venda, "status", "Concluída"),
                "forma_pagamento": getattr(venda, "forma_pagamento", "PIX"),
                "data_venda": _formatar_data_venda(getattr(venda, "data_venda", None)),
                "itens": itens,
            }
        )
    return resposta


def registrar_venda(db: Session, dados):
    payload = dados.model_dump() if hasattr(dados, "model_dump") else dict(dados)
    cliente = _normalizar_cliente(payload)
    itens = _normalizar_itens(payload)

    produto_id = None
    quantidade = 1
    preco_total = payload.get("preco_total") or payload.get("valor_total") or 0.0
    forma_pagamento = payload.get("forma_pagamento") or "PIX"

    if itens and isinstance(itens, list):
        primeiro_item = itens[0]
        produto_id = primeiro_item.get("produto_id")
        quantidade = primeiro_item.get("quantidade") or 1
        variacao_id = primeiro_item.get("variacao_id")

        if variacao_id:
            variacao = db.query(VariacaoProduto).filter(VariacaoProduto.id == variacao_id).first()
            if not variacao:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variação {variacao_id} não encontrada",
                )
            if variacao.estoque < quantidade:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Estoque insuficiente para a variação '{variacao.nome_variacao}'.",
                )
            if not primeiro_item.get("preco_unitario"):
                produto = db.query(Produto).filter(Produto.id == produto_id).first() if produto_id else None
                valor_base = float(produto.preco or 0.0) if produto else 0.0
                primeiro_item["preco_unitario"] = float((variacao.preco_adicional or 0.0) + valor_base)

        if not primeiro_item.get("preco_unitario") and produto_id is not None:
            produto = db.query(Produto).filter(Produto.id == produto_id).first()
            if produto:
                primeiro_item["preco_unitario"] = float(produto.preco or 0.0)

    if produto_id is not None:
        produto = db.query(Produto).filter(Produto.id == produto_id).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produto {produto_id} não encontrado",
            )

        if not preco_total or float(preco_total) <= 0:
            preco_total = float(produto.preco) * int(quantidade)

    nova_venda = Venda(
        cliente=cliente,
        comprador=cliente,
        produto_id=produto_id,
        quantidade=quantidade,
        valor_total=float(preco_total or 0.0),
        preco_total=float(preco_total or 0.0),
        forma_pagamento=forma_pagamento,
        status=payload.get("status") or "Concluída",
    )

    db.add(nova_venda)
    db.commit()
    db.refresh(nova_venda)

    if itens and isinstance(itens, list):
        for item in itens:
            item_produto_id = item.get("produto_id")
            item_variacao_id = item.get("variacao_id")
            if item_produto_id is None:
                continue

            produto = db.query(Produto).filter(Produto.id == item_produto_id).first()
            if not produto:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Produto {item_produto_id} não encontrado",
                )

            if item_variacao_id:
                variacao = db.query(VariacaoProduto).filter(VariacaoProduto.id == item_variacao_id).first()
                if not variacao:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Variação {item_variacao_id} não encontrada",
                    )
                if variacao.estoque < (item.get("quantidade") or 1):
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Estoque insuficiente para a variação '{variacao.nome_variacao}'.",
                    )
                variacao.estoque = variacao.estoque - (item.get("quantidade") or 1)

            novo_item = ItemVenda(
                venda_id=nova_venda.id,
                produto_id=item_produto_id,
                variacao_id=item_variacao_id,
                quantidade=item.get("quantidade") or 1,
                preco_unitario=float(item.get("preco_unitario") or produto.preco or 0.0),
            )
            db.add(novo_item)

    db.commit()
    db.refresh(nova_venda)
    return {
        "status": "sucesso",
        "mensagem": "Venda gravada!",
        "id": nova_venda.id,
        "cliente": cliente,
        "comprador": cliente,
    }
