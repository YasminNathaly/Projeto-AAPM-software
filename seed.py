import asyncio
from passlib.context import CryptContext

# Importações diretas dos arquivos de modelos
from app.database import engine, Base, SessionLocal
from app.models.usuario import Usuario
from app.models.categoria import Categoria
from app.models.produto import Produto

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# ... resto do código permanece o mesmo
def gerar_hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)

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
            Produto(nome="Semestralidade AAPM", tamanho="Fixa", preco=100.00, disponivel=True, imagem_url="", categoria_id=cat_taxas.id),
            Produto(nome="Armário + Semestralidade", tamanho="Anual", preco=130.00, disponivel=True, imagem_url="", categoria_id=cat_taxas.id),
            Produto(nome="2ª via de crachá", tamanho="Unidade", preco=15.00, disponivel=True, imagem_url="", categoria_id=cat_taxas.id),
            Produto(nome="CÓPIA (Preto e branco) unitário", tamanho="A4", preco=2.00, disponivel=True, imagem_url="", categoria_id=cat_taxas.id),
            
            # --- Uniformes ---
            Produto(nome="Avental", tamanho="Único", preco=58.00, disponivel=True, imagem_url="", categoria_id=cat_uniformes.id),
            Produto(nome="Avental de Oficina", tamanho="G", preco=58.00, disponivel=True, imagem_url="", categoria_id=cat_uniformes.id),
            Produto(nome="Bolsa SENAI", tamanho="Único", preco=36.50, disponivel=True, imagem_url="", categoria_id=cat_uniformes.id),
            Produto(nome="Camiseta malha Branca", tamanho="M", preco=35.00, disponivel=True, imagem_url="", categoria_id=cat_uniformes.id),
            Produto(nome="Camiseta malha Preta", tamanho="G", preco=35.00, disponivel=True, imagem_url="", categoria_id=cat_uniformes.id),
            Produto(nome="Camiseta POLO de malha preta", tamanho="GG", preco=55.00, disponivel=True, imagem_url="", categoria_id=cat_uniformes.id),
            Produto(nome="Touca protetora (5 un)", tamanho="Pacote", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_uniformes.id),
            
            # --- Ferramentas e Oficina ---
            Produto(nome="Agulha de máquina Nº11- pacote c/10un", tamanho="Nº11", preco=8.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Alfinete c/ cabeça colorida", tamanho="Caixa", preco=2.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Alfinete simples", tamanho="Caixa", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Alicate de Pic", tamanho="Único", preco=30.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Bobina", tamanho="Unidade", preco=1.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Caixa de bobina", tamanho="Unidade", preco=8.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Carretilha cabo de madeira", tamanho="Unidade", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Fita Métrica", tamanho="1.5m", preco=3.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Furador", tamanho="Unidade", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Guia Magnético G20", tamanho="Unidade", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Pinça Costura", tamanho="Unidade", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Passador de linha grande", tamanho="Unidade", preco=3.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Passador de linha pequeno", tamanho="Unidade", preco=1.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Tesoura", tamanho="Padrão", preco=18.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Tesoura Arremate", tamanho="Pequena", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Tesoura de Picotar Profissional", tamanho="Grande", preco=39.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Tesoura Picolar escolar", tamanho="Média", preco=12.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            Produto(nome="Vazador 2mm", tamanho="2mm", preco=14.00, disponivel=True, imagem_url="", categoria_id=cat_ferramentas.id),
            
            # --- Papelaria, Desenho e Materiais ---
            Produto(nome="Almofada Alfineteira Tomate", tamanho="Unidade", preco=6.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Apontador", tamanho="Unidade", preco=3.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Apostila Têxtil", tamanho="Único", preco=29.90, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Borracha Artística", tamanho="Unidade", preco=9.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Borracha branca", tamanho="Unidade", preco=2.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Borracha Caneta", tamanho="Unidade", preco=11.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Calculadora", tamanho="Unidade", preco=14.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Caneta BIC", tamanho="Unidade", preco=1.30, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Caneta Mágica fantasminha colorida", tamanho="Unidade", preco=8.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Caneta Marca Texto", tamanho="Unidade", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Caneta para desenho Faber Castell 0.4", tamanho="0.4mm", preco=8.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Canetinha colorida c/ 12 cores", tamanho="Estojo", preco=8.50, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Clips Nr 3/0", tamanho="Caixa", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Cola bastão 10g", tamanho="10g", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Corretivo (Fita Corretiva)", tamanho="Unidade", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Cola Líquida", tamanho="Unidade", preco=4.50, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Compasso", tamanho="Unidade", preco=13.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Curva Francesa grande 1119", tamanho="Grande", preco=19.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Curva Francesa pequena 1105", tamanho="Pequena", preco=15.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Durex", tamanho="Unidade", preco=3.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Esfruminho", tamanho="Unidade", preco=5.50, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Esquadro", tamanho="Unidade", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Estojo Organizador M", tamanho="Médio", preco=17.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Fita Crepe - rolo 18mm x 10m", tamanho="10m", preco=2.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Fita Crepe - rolo 18mm x 50m", tamanho="50m", preco=8.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Giz lápis marcar tecido cores", tamanho="Caixa", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Grafite Faber Castell e HB", tamanho="Tubo", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Grafite Leo&Leo 0.5, 0.7 e 0.9mm", tamanho="Tubo", preco=3.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Grampeador pequeno", tamanho="Unidade", preco=9.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Grampo para grampeador cx. c/1000un", tamanho="Caixa", preco=2.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Lápis HB nº2 e nº4", tamanho="Unidade", preco=1.50, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Lapiseira 0.7mm", tamanho="0.7mm", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Lapiseira 0.9mm", tamanho="0.9mm", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Lapiseira 2.0mm", tamanho="2.0mm", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Lente Conta Fio", tamanho="Unidade", preco=35.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Papel Canson", tamanho="Bloco", preco=12.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Papel Kraft - rolo 10 metros", tamanho="10m", preco=16.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Papel Kraft Folha unitária", tamanho="Folha", preco=2.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Papel Sulfite c/100f", tamanho="Pacote", preco=8.50, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Pasta com aba e elástico", tamanho="Unidade", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Percevejos", tamanho="Caixa", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Porta crachá", tamanho="Unidade", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Régua 15cm", tamanho="15cm", preco=3.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Régua 3 em 1", tamanho="Kit", preco=65.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Régua 30cm", tamanho="30cm", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Régua Curvas", tamanho="Unidade", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Régua mm 30cm", tamanho="30cm", preco=17.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            Produto(nome="Régua mm 60cm", tamanho="60cm", preco=28.00, disponivel=True, imagem_url="", categoria_id=cat_papelaria.id),
            
            # --- Lazer, Diversos e Eletrônicos ---
            Produto(nome="Abridor de casa", tamanho="Unidade", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Bolinha de Pebolim (un)", tamanho="Unidade", preco=5.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Bolinha de Ping Pong (un)", tamanho="Unidade", preco=2.50, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Bolinha de Ping Pong (pacote com 4un)", tamanho="Pacote", preco=9.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Cordão para crachá SENAI", tamanho="Unidade", preco=4.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Carregador de Celular V8 USB", tamanho="Eletrônico", preco=14.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Cabo USB tipo C", tamanho="Eletrônico", preco=10.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Fone de Ouvido", tamanho="Eletrônico", preco=8.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Óculos de sobrepor 3M", tamanho="Segurança", preco=28.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Óculos simples 3M", tamanho="Segurança", preco=15.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
            Produto(nome="Protetor auricular", tamanho="Segurança", preco=7.00, disponivel=True, imagem_url="", categoria_id=cat_lazer.id),
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