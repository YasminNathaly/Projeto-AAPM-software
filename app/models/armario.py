from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base

class Armario(Base):
    __tablename__ = "armarios"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, nullable=False, unique=True)
    localizacao = Column(String, nullable=True)
    status = Column(String, default="Disponível")
    
    nome_completo = Column(String, nullable=True)
    curso = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=True)
