from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.controllers import produto_controller

router = APIRouter(prefix="/produtos")


@router.get("/api/produtos")
def api_produtos(db: Session = Depends(get_db)):
    return produto_controller.listar_produtos(db)

