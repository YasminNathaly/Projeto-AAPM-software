from fastapi import APIRouter

router = APIRouter(prefix="/assistente", tags=["Assistente"])

@router.get("/")
def index():
    return {"message": "Assistente ativo"}