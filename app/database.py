import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Caminho para salvar o arquivo do banco 'aapm.db' na raiz do seu projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "aapm.db")

# 2. URL de conexão com o SQLite
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# Cria o engine com a flag do SQLite para suportar múltiplas threads do FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# Configura a sessão do banco
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para a criação dos modelos
Base = declarative_base()

# Função para obter a sessão do banco (Injeção de dependência)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()