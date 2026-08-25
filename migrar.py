import sqlite3

# Importante: Veja no seu database.py qual é o nome exato do arquivo .db
# Exemplo: 'sql_app.db', 'app.db', 'database.db', etc.
NOME_DO_BANCO = "sql_app.db" 

def migrar_categorias():
    conn = sqlite3.connect(NOME_DO_BANCO)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE categorias ADD COLUMN codigo TEXT;")
        conn.commit()
        print("Coluna 'codigo' adicionada com sucesso na tabela 'categorias'!")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("A coluna 'codigo' já existe na tabela 'categorias'.")
        elif "no such table" in str(e).lower():
            print(f"Erro: A tabela 'categorias' não foi encontrada no arquivo '{NOME_DO_BANCO}'.")
            print("Verifique se o nome do arquivo .db na variável NOME_DO_BANCO está correto.")
        else:
            print(f"Erro: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrar_categorias()