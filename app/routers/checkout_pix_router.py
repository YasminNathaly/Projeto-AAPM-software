import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.produto import Produto
from app.models.venda import ItemVenda, Venda

try:
    from app.models.variacao import VariacaoProduto
except ImportError:
    VariacaoProduto = None

router = APIRouter(prefix="/api/checkout/pix", tags=["Checkout PIX"])


class PixItemInput(BaseModel):
    produto_id: int
    variacao_id: Optional[int] = None
    quantidade: int = 1


class PixCheckoutRequest(BaseModel):
    cliente: str = "Cliente Loja Online"
    email: Optional[str] = None
    itens: List[PixItemInput]


def _calcular_crc16_pix(payload: str) -> str:
    crc = 0xFFFF
    for ch in payload.encode("utf-8"):
        crc ^= ch << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _gerar_emv_pix(valor: float, txid: str) -> str:
    chave_pix = os.getenv("PIX_CHAVE", "aapm@sp.senai.br")
    recebedor = os.getenv("PIX_RECEBEDOR", "AAPM SENAI BRAS")[:25]
    cidade = os.getenv("PIX_CIDADE", "SAO PAULO")[:15]
    valor_str = f"{valor:.2f}"

    gui = "0014br.gov.bcb.pix"
    campo_chave = f"01{len(chave_pix):02d}{chave_pix}"
    merchant_info = f"{gui}{campo_chave}"
    campo_26 = f"26{len(merchant_info):02d}{merchant_info}"

    campo_52 = "52040000"
    campo_53 = "5303986"
    campo_54 = f"54{len(valor_str):02d}{valor_str}"
    campo_58 = "5802BR"
    campo_59 = f"59{len(recebedor):02d}{recebedor}"
    campo_60 = f"60{len(cidade):02d}{cidade}"

    txid_limpo = "".join(c for c in txid if c.isalnum())[:25] or "SENAIBRAS"
    sub_txid = f"05{len(txid_limpo):02d}{txid_limpo}"
    campo_62 = f"62{len(sub_txid):02d}{sub_txid}"

    sem_crc = f"000201{campo_26}{campo_52}{campo_53}{campo_54}{campo_58}{campo_59}{campo_60}{campo_62}6304"
    return sem_crc + _calcular_crc16_pix(sem_crc)


def _confirmar_e_baixar_estoque(db: Session, venda: Venda) -> dict:
    if (venda.status or "").strip().lower() in {"concluída", "concluida", "pago"}:
        return {
            "status": "Concluída",
            "venda_id": venda.id,
            "mensagem": "Pagamento PIX já confirmado anteriormente.",
        }

    itens = db.query(ItemVenda).filter(ItemVenda.venda_id == venda.id).all()
    if itens:
        for item in itens:
            produto = db.query(Produto).filter(Produto.id == item.produto_id).first()
            if produto:
                qtd_atual = int(getattr(produto, "quantidade", None) or getattr(produto, "estoque", 0) or 0)
                novo_saldo = max(0, qtd_atual - int(item.quantidade or 1))
                if hasattr(produto, "quantidade"):
                    produto.quantidade = novo_saldo
                if hasattr(produto, "estoque"):
                    produto.estoque = novo_saldo
                if novo_saldo == 0 and hasattr(produto, "disponivel"):
                    produto.disponivel = False

            if item.variacao_id and VariacaoProduto:
                variacao = db.query(VariacaoProduto).filter(VariacaoProduto.id == item.variacao_id).first()
                if variacao:
                    variacao.estoque = max(0, int(variacao.estoque or 0) - int(item.quantidade or 1))
    elif venda.produto_id:
        produto = db.query(Produto).filter(Produto.id == venda.produto_id).first()
        if produto:
            qtd_atual = int(getattr(produto, "quantidade", None) or getattr(produto, "estoque", 0) or 0)
            novo_saldo = max(0, qtd_atual - int(venda.quantidade or 1))
            if hasattr(produto, "quantidade"):
                produto.quantidade = novo_saldo
            if hasattr(produto, "estoque"):
                produto.estoque = novo_saldo
            if novo_saldo == 0 and hasattr(produto, "disponivel"):
                produto.disponivel = False

    venda.status = "Concluída"
    db.commit()
    db.refresh(venda)
    return {
        "status": "Concluída",
        "venda_id": venda.id,
        "mensagem": "Pagamento PIX confirmado e estoque atualizado automaticamente!",
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_cobranca_pix(dados: PixCheckoutRequest, db: Session = Depends(get_db)):
    if not dados.itens:
        raise HTTPException(status_code=400, detail="O carrinho está vazio.")

    cliente_nome = (dados.cliente or "").strip() or "Cliente Loja Online"
    total = 0.0
    itens_validados = []

    for item in dados.itens:
        qtd = max(1, int(item.quantidade or 1))
        produto = db.query(Produto).filter(Produto.id == item.produto_id).first()
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto {item.produto_id} não encontrado.")

        estoque_disp = int(getattr(produto, "quantidade", None) or getattr(produto, "estoque", 0) or 0)
        if estoque_disp < qtd:
            raise HTTPException(
                status_code=400,
                detail=f"Estoque insuficiente para '{produto.nome}' (disponível: {estoque_disp}).",
            )

        preco_unit = float(produto.preco or 0.0)
        if item.variacao_id and VariacaoProduto:
            variacao = db.query(VariacaoProduto).filter(VariacaoProduto.id == item.variacao_id).first()
            if variacao:
                if int(variacao.estoque or 0) < qtd:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Estoque insuficiente para '{produto.nome} ({variacao.nome_variacao})'.",
                    )
                preco_unit += float(variacao.preco_adicional or 0.0)

        total += preco_unit * qtd
        itens_validados.append((produto, item.variacao_id, qtd, preco_unit))

    primeiro_prod, _, primeira_qtd, _ = itens_validados[0]
    nova_venda = Venda(
        cliente=cliente_nome,
        comprador=cliente_nome,
        produto_id=primeiro_prod.id,
        quantidade=primeira_qtd,
        valor_total=round(total, 2),
        preco_total=round(total, 2),
        forma_pagamento="PIX",
        status="Pendente PIX",
    )
    db.add(nova_venda)
    db.commit()
    db.refresh(nova_venda)

    for produto, var_id, qtd, preco_unit in itens_validados:
        db.add(
            ItemVenda(
                venda_id=nova_venda.id,
                produto_id=produto.id,
                variacao_id=var_id,
                quantidade=qtd,
                preco_unitario=preco_unit,
            )
        )
    db.commit()

    txid = f"SENAIBRAS{nova_venda.id:06d}"
    pix_copia_cola = _gerar_emv_pix(total, txid)

    return {
        "venda_id": nova_venda.id,
        "txid": txid,
        "status": nova_venda.status,
        "valor_total": round(total, 2),
        "pix_copia_cola": pix_copia_cola,
    }


@router.get("/{venda_id}")
def consultar_status_pix(venda_id: int, db: Session = Depends(get_db)):
    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido PIX não encontrado.")
    return {
        "venda_id": venda.id,
        "status": venda.status,
        "valor_total": float(venda.valor_total or venda.preco_total or 0.0),
        "cliente": venda.cliente or venda.comprador,
    }


@router.post("/webhook/{venda_id}")
def webhook_confirmar_pix_por_id(venda_id: int, db: Session = Depends(get_db)):
    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido PIX não encontrado.")
    return _confirmar_e_baixar_estoque(db, venda)


@router.post("/webhook")
async def webhook_gateway_pix(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    venda_id = payload.get("venda_id") or payload.get("external_reference")
    txid = str(payload.get("txid") or "")

    if not venda_id and txid.startswith("SENAIBRAS"):
        try:
            venda_id = int(txid.replace("SENAIBRAS", ""))
        except ValueError:
            venda_id = None

    if not venda_id:
        raise HTTPException(status_code=400, detail="Identificador da venda não informado no webhook.")

    venda = db.query(Venda).filter(Venda.id == int(venda_id)).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")

    status_recebido = str(payload.get("status") or "approved").lower()
    if status_recebido in {"approved", "paid", "concluida", "concluída", "pago"}:
        return _confirmar_e_baixar_estoque(db, venda)

    return {"status": venda.status, "venda_id": venda.id}
