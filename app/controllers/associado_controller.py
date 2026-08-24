import math
from fastapi import Request, HTTPException, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
# Substitua 'Associado' pelo nome correto da sua classe Model se for 'Usuario'
from app.models.usuario import Usuario as Associado 

templates = Jinja2Templates(directory="app/templates")

def listar_associados_page(db: Session, request: Request, page: int = 1, limit: int = 10):
    """Calcula a paginação e renderiza a view HTML com os associados."""
    offset = (page - 1) * limit
    
    total_items = db.query(Associado).count()
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 1
    
    associados = db.query(Associado).offset(offset).limit(limit).all()
    
    return templates.TemplateResponse(
        "admin/admin.html",
        {
            "request": request,
            "associados": associados,
            "page": page,
            "total_pages": total_pages
        }
    )

def obter_por_id(db: Session, associado_id: int):
    associado = db.query(Associado).filter(Associado.id == associado_id).first()
    if not associado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Associado não encontrado"
        )
    return associado

def criar(db: Session, dados: dict):
    novo_associado = Associado(**dados)
    db.add(novo_associado)
    db.commit()
    db.refresh(novo_associado)
    return novo_associado

def atualizar(db: Session, associado_id: int, dados: dict):
    associado = obter_por_id(db, associado_id)
    for chave, valor in dados.items():
        if valor is not None:
            setattr(associado, chave, valor)
    db.commit()
    db.refresh(associado)
    return associado

def deletar(db: Session, associado_id: int):
    associado = obter_por_id(db, associado_id)
    db.delete(associado)
    db.commit()
    return True