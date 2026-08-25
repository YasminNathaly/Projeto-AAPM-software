import asyncio
import bcrypt
from passlib.context import CryptContext

# Importações dos modelos do banco
from app.database import engine, Base, SessionLocal
from app.models.usuario import Usuario
from app.models.categoria import Categoria
from app.models.produto import Produto
from app.models.associado import Associado
from app.models.venda import Venda
from app.models.armario import Armario  # <-- Importado o modelo Armario

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def gerar_hash_senha(senha: str) -> str:
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
            # Adicione seus produtos aqui caso queira
        ]
        if produtos_oficiais:
            db.add_all(produtos_oficiais)

        # 4. ASSOCIADOS DE TESTE
        print("👥 Inserindo associados no banco...")
        assoc1 = Associado(
            nome="Carlos Eduardo Silva",
            email="carlos.silva@email.com",
            telefone="11999998888",
            endereco="Rua das Flores, 123"
        )
        assoc2 = Associado(
            nome="Mariana Oliveira Souza",
            email="mariana.souza@email.com",
            telefone="11977776666",
            endereco="Av. Brasil, 456"
        )
        db.add_all([assoc1, assoc2])

        # 5. ARMÁRIOS DE TESTE (Usando nome_completo)
        print("🚪 Inserindo armários de teste...")
        arm1 = Armario(
            numero="001",
            localizacao="Bloco A, Corredor 1",
            status="Ocupado",
            nome_completo="João da Silva"
        )
        arm2 = Armario(
            numero="002",
            localizacao="Bloco A, Corredor 1",
            status="Disponível",
            nome_completo=None
        )
        db.add_all([arm1, arm2])

        # Confirma todas as inserções no banco
        db.commit()
        print("🚀 Sucesso! Banco populado com sucesso.")

    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao popular banco de dados: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(popular_banco_dados())