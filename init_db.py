# init_db.py
import sqlite3

# Conecta ao banco de dados (cria o arquivo se não existir)
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Cria a tabela para armazenar o feedback
# TEXT armazena a resposta discursiva
# SWOT_DATA armazena os resultados do teste que geraram esse feedback
cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resposta_discursiva TEXT NOT NULL,
        swot_data TEXT,
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

print("Tabela 'feedback' criada com sucesso no arquivo database.db.")

conn.commit()
conn.close()