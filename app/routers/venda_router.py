from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db

# Importações dos modelos com fallback
try:
    from app.models.venda import Venda
except ImportError:
    Venda = None

try:
    from app.models.produto import Produto
except ImportError:
    Produto = None

router = APIRouter(
    prefix="/api/vendas",
    tags=["Vendas"]
)

class VendaSchema(BaseModel):
    comprador: str
    produto_id: Optional[int] = None
    quantidade: int
    preco_total: float

@router.get("/")
@router.get("")
async def listar_vendas(db: Session = Depends(get_db)):
    if not Venda:
        return []
    vendas = db.query(Venda).order_by(Venda.id.desc()).all()
    res = []
    for v in vendas:
        nome_prod = "Produto Indisponível"
        if Produto and getattr(v, "produto_id", None):
            prod = db.query(Produto).filter(Produto.id == v.produto_id).first()
            if prod:
                nome_prod = prod.nome
        res.append({
            "id": v.id,
            "comprador": getattr(v, "comprador", ""),
            "produto_id": getattr(v, "produto_id", None),
            "produto_nome": nome_prod,
            "quantidade": getattr(v, "quantidade", 0),
            "preco_total": getattr(v, "preco_total", 0.0),
            "data_venda": getattr(v, "data_venda", "")
        })
    return res

@router.post("/")
@router.post("")
async def registrar_venda(dados: VendaSchema, db: Session = Depends(get_db)):
    if not Venda:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, 
            detail="O modelo Venda não foi importado corretamente."
        )

    # Criação garantida do objeto no banco
    nova_venda = Venda()
    
    # Preenchimento dinâmico para evitar divergência de nomes de colunas no modelo
    if hasattr(nova_venda, "comprador"):
        nova_venda.comprador = dados.comprador
    if hasattr(nova_venda, "produto_id"):
        nova_venda.produto_id = dados.produto_id
    if hasattr(nova_venda, "quantidade"):
        nova_venda.quantidade = dados.quantidade
    if hasattr(nova_venda, "preco_total"):
        nova_venda.preco_total = dados.preco_total
    elif hasattr(nova_venda, "valor_total"):
        nova_venda.valor_total = dados.preco_total

    try:
        db.add(nova_venda)
        db.commit()          # Persiste os dados no banco de dados MySQL
        db.refresh(nova_venda)
        return {"status": "sucesso", "mensagem": "Venda gravada!", "id": nova_venda.id}
    except Exception as e:
        db.rollback()        # Desfaz em caso de erro de gravação
        print(f"❌ Erro ao gravar venda no banco: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao salvar a venda: {str(e)}"
        )