import asyncio
import bcrypt
from passlib.context import CryptContext

# Importações dos modelos do banco
from app.database import engine, Base, SessionLocal
from app.models.usuario import Usuario
from app.models.categoria import Categoria
from app.models.produto import Produto
from app.models.associado import Associado
from app.models.venda import Venda, ItemVenda
from app.models.armario import Armario

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
        db.add_all([admin, funcionario])
        db.flush()

        # 2. CATEGORIAS
        print("🗂️ Criando categorias...")
        cat_uniformes = Categoria(nome="Uniformes")
        cat_papelaria = Categoria(nome="Papelaria e Desenho")
        db.add_all([cat_uniformes, cat_papelaria])
        db.flush()

        # 3. PRODUTOS DE TESTE
        print("👕 Inserindo produtos de teste...")
        prod1 = Produto(nome="Camiseta SENAI M", preco=50.0, categoria_id=cat_uniformes.id, estoque=20)
        prod2 = Produto(nome="Caderno Universitario", preco=20.0, categoria_id=cat_papelaria.id, estoque=50)
        db.add_all([prod1, prod2])
        db.flush()

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
        db.flush()

        # 5. ARMÁRIOS DE TESTE
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

        # 6. VENDAS DE TESTE (Sem desconto vs Com desconto)
        print("🛒 Inserindo vendas de teste...")
        
        # Venda 1: Cliente comum (sem desconto)
        venda_comum = Venda(
            cliente="Cliente Balcão",
            comprador="Cliente Balcão",
            produto_id=prod1.id,
            quantidade=1,
            forma_pagamento="PIX",
            associado_id=None,
            desconto_percentual=0.0,
            valor_desconto=0.0,
            valor_total=50.0,
            preco_total=50.0,
            status="Concluída"
        )

        # Venda 2: Associado Carlos Eduardo (10% de desconto -> R$ 5,00 off)
        subtotal = prod1.preco * 1  # 50.00
        desconto = subtotal * 0.10  # 5.00
        total_com_desconto = subtotal - desconto  # 45.00

        venda_associado = Venda(
            cliente=assoc1.nome,
            comprador=assoc1.nome,
            produto_id=prod1.id,
            quantidade=1,
            forma_pagamento="PIX",
            associado_id=assoc1.id,
            desconto_percentual=10.0,
            valor_desconto=desconto,
            valor_total=total_com_desconto,
            preco_total=total_com_desconto,
            status="Concluída"
        )

        db.add_all([venda_comum, venda_associado])
        db.flush()

        # Itens das vendas
        item1 = ItemVenda(venda_id=venda_comum.id, produto_id=prod1.id, quantidade=1, preco_unitario=50.0)
        item2 = ItemVenda(venda_id=venda_associado.id, produto_id=prod1.id, quantidade=1, preco_unitario=50.0)
        db.add_all([item1, item2])

        db.commit()
        print("🚀 Sucesso! Banco populado com sucesso.")

    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao popular banco de dados: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(popular_banco_dados())