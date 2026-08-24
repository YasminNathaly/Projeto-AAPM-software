import sqlite3

# Substitua 'seu_banco.db' pelo nome real do seu arquivo de banco SQLite
NOME_DO_BANCO = "aapm.db" 

def migrar():
    conn = sqlite3.connect(NOME_DO_BANCO)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE vendas ADD COLUMN associado_id INTEGER REFERENCES associados(id);")
        conn.commit()
        print("Coluna 'associado_id' adicionada com sucesso na tabela 'vendas'!")
    except Exception as e:
        print(f"Erro ao migrar: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrar()