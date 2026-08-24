from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Armario(Base):
    __tablename__ = "armarios"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, nullable=False, unique=True)
    localizacao = Column(String, nullable=True)
    status = Column(String, default="Disponível")
    
    associado_id = Column(Integer, ForeignKey("associados.id"), nullable=True)

    @property
    def associado_nome(self):
        return self.associado.nome if hasattr(self, "associado") and self.associado else None