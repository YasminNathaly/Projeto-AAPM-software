import sqlite3

# Abra a conexão com o arquivo .db do seu projeto
# Ajuste o nome 'sql_app.db' para o nome exato do seu arquivo SQLite
conn = sqlite3.connect("sql_app.db") 
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE fornecedores ADD COLUMN documento TEXT;")
    conn.commit()
    print("Coluna 'documento' adicionada com sucesso!")
except sqlite3.OperationalError as e:
    print(f"Aviso/Erro: {e}")
finally:
    conn.close()