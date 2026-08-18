import asyncio
from passlib.context import CryptContext

# Importações diretas dos arquivos de modelos
from app.database import engine, Base, SessionLocal
from app.models.usuario import Usuario
from app.models.categoria import Categoria
from app.models.produto import Produto
import bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# ... resto do código permanece o mesmo
def gerar_hash_senha(senha: str) -> str:
    # Garante que a senha não passe de 72 bytes
    senha_bytes = senha.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_bytes, salt).decode('utf-8')

async def popular_banco_dados():
    print("🔄 Limpando e recriando tabelas no banco de dados...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. USUÁRIOS E ROLES
        print("👥 Inserindo usuários obrigatórios...")
        senha_hash = gerar_hash_senha("Senai123!")
        
        admin = Usuario(
            nome="Coordenador Geral",
            email="admin@sp.senai.br",
            senha=senha_hash,
            role="ADMIN",
            ativo=True
        )
        funcionario = Usuario(
            nome="Atendente Secretaria",
            email="aapm@sp.senai.br",
            senha=senha_hash,
            role="FUNCIONARIO",
            ativo=True
        )
        db.add(admin)
        db.add(funcionario)
        db.flush()

        # 2. CATEGORIAS OFICIAIS DA AAPM
        print("🗂️ Criando categorias organizadas...")
        cat_taxas = Categoria(nome="Taxas e Serviços")
        cat_uniformes = Categoria(nome="Uniformes")
        cat_papelaria = Categoria(nome="Papelaria e Desenho")
        cat_ferramentas = Categoria(nome="Ferramentas e Oficina")
        cat_lazer = Categoria(nome="Lazer e Diversos")
        
        db.add_all([cat_taxas, cat_uniformes, cat_papelaria, cat_ferramentas, cat_lazer])
        db.flush()

        # 3. EXTRAÇÃO COMPLETA DA SUA LISTA DE MATERIAIS AAPM
        print("👕 Inserindo catálogo massivo extraído da AAPM...")
        
        produtos_oficiais = [
            # --- Taxas e Serviços ---
            
            
            # --- Ferramentas e Oficina ---
            
        ]

        db.add_all(produtos_oficiais)
        db.commit()
        print(f"🚀 Sucesso! Banco populado com {len(produtos_oficiais)} produtos reais da AAPM.")

    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao popular banco de dados: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(popular_banco_dados())