from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)

# --- INÍCIO DA IMPLEMENTAÇÃO DO FLUXOGRAMA (Mantido como estava) ---
MIN_ATIVAR_TRACOS = {
    "Reatividade a Mudanças": 3,
}

SWOT_CLASSIFICACAO_TRACOS = {
    "Reatividade a Mudanças": "T",
}

def classificar_traco_fluxograma(nome_do_traco: str, user_freq: int) -> str:
    if nome_do_traco not in MIN_ATIVAR_TRACOS or nome_do_traco not in SWOT_CLASSIFICACAO_TRACOS:
        return f"Erro: Traço '{nome_do_traco}' não encontrado nos dados de referência."

    min_ativar_valor = MIN_ATIVAR_TRACOS[nome_do_traco]
    swot_valor = SWOT_CLASSIFICACAO_TRACOS[nome_do_traco]

    if user_freq >= min_ativar_valor:
        if swot_valor == "T":
            return "AMEAÇA"
        else:
            return "OPORTUNIDADE"
    else:
        return "NEUTRO"
# --- FIM DA IMPLEMENTAÇÃO DO FLUXOGRAMA ---


# Função para inicializar o banco de dados
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        idade INTEGER,
        email TEXT,
        pontuacao_total INTEGER,
        grupo INTEGER,
        intensidade_emocional TEXT -- Nova coluna para armazenar a cor
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS perguntas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enunciado TEXT,
        alternativa_a TEXT,
        alternativa_b TEXT,
        alternativa_c TEXT,
        alternativa_d TEXT,
        resposta_correta TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        pergunta_id INTEGER, -- Este ID pode ser usado para identificar a pergunta da cor também
        resposta TEXT,
        pontuacao INTEGER
    )
    ''')
    
    conn.commit()
    conn.close()

if not os.path.exists('database.db'):
    init_db()
else:
    # Garante que a coluna 'intensidade_emocional' existe na tabela 'usuarios'
    # Esta é uma migração simples. Em produção, use ferramentas de migração de DB.
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN intensidade_emocional TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name: intensidade_emocional" not in str(e):
            raise
    # Limpa todas as perguntas na tabela 'perguntas' se não houver outras.
    cursor.execute('DELETE FROM perguntas') 
    conn.commit()
    conn.close()


def classificar_usuario(resposta_condicional: str, frequencia_codigo: str = None, intensidade_emocional: str = None): # Adicionado intensidade_emocional
    """
    Classifica o usuário com base nas suas respostas, utilizando a lógica do fluxograma.
    """
    grupo = 0
    mensagem = ""
    nome_do_traço = "Reatividade a Mudanças" 

    if resposta_condicional == 'nao':
        classificacao_fluxograma = "NEUTRO"
        grupo = 1 
        mensagem = "Agradecemos sua resposta. Não se identificar com esta situação é um dado importante. Continue explorando nosso conteúdo para mais informações."
    elif resposta_condicional == 'sim':
        freq_map_to_numeric = {
            'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5
        }
        
        user_freq = freq_map_to_numeric.get(frequencia_codigo, 0) 
        classificacao_fluxograma = classificar_traco_fluxograma(nome_do_traço, user_freq)

        # AQUI VOCÊ PODE INTEGRAR A LÓGICA DA COR NA CLASSIFICAÇÃO
        # Por exemplo, se a cor for "vermelho" (alta intensidade), pode-se ajustar o grupo ou a mensagem.
        # Exemplo simples:
        # if intensidade_emocional == 'vermelho' and classificacao_fluxograma == "OPORTUNIDADE":
        #    classificacao_fluxograma = "AMEAÇA" # Altera a classificação se a emoção é intensa
        
        # Ou simplesmente usar a cor para refinar a mensagem dentro de cada grupo
        if classificacao_fluxograma == "AMEAÇA":
            grupo = 4 
            mensagem = "Entendemos que esta é uma experiência frequente para você. Isso aponta para uma necessidade de suporte substancial. Recomendamos buscar orientação profissional para encontrar as melhores estratégias de manejo e apoio."
            if intensidade_emocional == 'vermelho':
                mensagem += " A intensidade alta das emoções indica uma urgência ainda maior."
            elif intensidade_emocional == 'laranja':
                mensagem += " A intensidade moderada das emoções sugere que a situação é significativa."
        elif classificacao_fluxograma == "OPORTUNIDADE":
            if user_freq >= 3: 
                grupo = 3 
                mensagem = "Compreendemos. Vivenciar isso ocasionalmente indica uma necessidade de suporte moderado. Explorar estratégias e, se necessário, buscar acompanhamento profissional pode ser muito útil."
            else: 
                grupo = 2 
                mensagem = "Sua experiência é válida. Sentir isso raramente ou quase nunca sugere uma necessidade de suporte leve para lidar com esses desafios. Pequenas adaptações podem fazer uma grande diferença."
            
            if intensidade_emocional == 'vermelho':
                mensagem += " No entanto, a intensidade alta das emoções merece atenção, mesmo em um contexto de oportunidade."
            elif intensidade_emocional == 'laranja':
                mensagem += " A intensidade moderada das emoções reforça a importância de explorar as estratégias."

        elif classificacao_fluxograma == "NEUTRO":
            grupo = 1 
            mensagem = "Sua experiência é válida, mas a frequência indicada sugere que o impacto é mínimo. Continue explorando nosso conteúdo para mais informações."
            # Talvez, mesmo neutro, uma emoção vermelha indique algo? Depende da sua lógica.

        else:
            grupo = 5
            mensagem = classificacao_fluxograma 
    else: 
        grupo = 5
        mensagem = "Houve um problema com a sua resposta condicional. Por favor, tente novamente."

    return grupo, mensagem

@app.route('/')
def home():
    return redirect(url_for('formulario'))

@app.route('/formulario', methods=['GET', 'POST'])
def formulario():
    # Não precisamos mais buscar perguntas do DB para a história da Clara
    # perguntas_db = cursor.execute('SELECT id, enunciado, alternativa_a, alternativa_b, alternativa_c, alternativa_d FROM perguntas').fetchall()
    
    if request.method == 'POST':
        conn_write = sqlite3.connect('database.db')
        cursor_write = conn_write.cursor()

        # Captura a resposta da nova pergunta de cor
        intensidade_emocional = request.form.get('intensidade_emocional')

        cursor_write.execute('INSERT INTO usuarios (nome, idade, email, pontuacao_total, grupo, intensidade_emocional) VALUES (?, ?, ?, ?, ?, ?)',
                             (None, None, None, 0, 0, intensidade_emocional)) # Adicionado intensidade_emocional
        usuario_id = cursor_write.lastrowid

        resposta_condicional = request.form.get('resposta_condicional')
        frequencia_codigo = request.form.get('frequencia') 
        
        pergunta_historia_id = 1 # ID fixo para a pergunta da história da Clara

        ponto_para_resposta_db = 0
        resposta_para_db = resposta_condicional

        if resposta_condicional == 'sim' and frequencia_codigo:
            pontos_db_frequencia = {
                'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5
            }
            ponto_para_resposta_db = pontos_db_frequencia.get(frequencia_codigo, 0)
            resposta_para_db = 'sim_' + frequencia_codigo

        cursor_write.execute('INSERT INTO respostas (usuario_id, pergunta_id, resposta, pontuacao) VALUES (?, ?, ?, ?)',
                             (usuario_id, pergunta_historia_id, resposta_para_db, ponto_para_resposta_db))
        
        # Chama a função classificar_usuario passando a nova informação de intensidade
        grupo, mensagem_personalizada = classificar_usuario(resposta_condicional, frequencia_codigo, intensidade_emocional)
        
        cursor_write.execute('UPDATE usuarios SET pontuacao_total=?, grupo=?, intensidade_emocional=? WHERE id=?',
                             (ponto_para_resposta_db, grupo, intensidade_emocional, usuario_id)) # Atualizado para salvar a intensidade também

        conn_write.commit()
        conn_write.close()

        return redirect(url_for('resultado', grupo=grupo, mensagem=mensagem_personalizada))

    return render_template('formulario.html')

@app.route('/resultado')
def resultado():
    grupo = request.args.get('grupo')
    mensagem = request.args.get('mensagem')
    return render_template('resultado.html', grupo=grupo, mensagem=mensagem)

if __name__ == '__main__':
    app.run(debug=True, port=int(os.environ.get('PORT', 5001)))
