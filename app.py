from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)

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
        grupo INTEGER
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
        pergunta_id INTEGER,
        resposta TEXT,
        pontuacao INTEGER
    )
    ''')

    # HISTÓRIA DA CLARA - APENAS A HISTÓRIA, SEM A PERGUNTA CONDICIONAL NO FINAL
    perguntas_data = [
        ("Clara, 28 anos, mora com os pais e o irmão mais novo. Era um fim de semana e ela estava animada para passar a tarde ouvindo música e organizando sua coleção de livros, uma atividade que a ajudava a relaxar. Mas, logo após o café da manhã, em sua casa, sua mãe avisou que a tia viria visitar e queria usar o quarto de Clara para descansar. Assim que ouviu aquilo, algo dentro dela se embaralhou. O peito apertou, os olhos arderam, e a voz saiu alta, quase gritando: “Sempre mudam tudo! Nunca me avisam antes!” Sem pensar muito, ela bateu a porta do quarto. Em seguida, se encolheu na cama, sentindo-se dominada por uma mistura de raiva, culpa e tristeza. Ela fica na cama até a visita chegar.", "Sim", "Não", "", "", "")
    ]

    cursor.execute('DELETE FROM perguntas')
    cursor.executemany('''
    INSERT INTO perguntas (enunciado, alternativa_a, alternativa_b, alternativa_c, alternativa_d, resposta_correta)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', perguntas_data)

    conn.commit()
    conn.close()

# Verifica se o banco de dados existe, se não, inicializa
if not os.path.exists('database.db'):
    init_db()

def classificar_usuario(resposta_condicional, frequencia=None):
    grupo = 0
    mensagem = ""

    if resposta_condicional == 'nao':
        grupo = 1 # Grau 1: Nenhuma identificação com a situação
        mensagem = "Agradecemos sua resposta. Não se identificar com esta situação é um dado importante. Continue explorando nosso conteúdo para mais informações."
    elif resposta_condicional == 'sim':
        if frequencia == 'a' or frequencia == 'b': # Quase Nunca, Raramente
            grupo = 2 # Grau 2: Indicação de suporte leve
            mensagem = "Sua experiência é válida. Sentir isso raramente ou quase nunca sugere uma necessidade de suporte leve para lidar com esses desafios. Pequenas adaptações podem fazer uma grande diferença."
        elif frequencia == 'c': # Ocasionalmente
            grupo = 3 # Grau 3: Indicação de suporte moderado
            mensagem = "Compreendemos. Vivenciar isso ocasionalmente indica uma necessidade de suporte moderado. Explorar estratégias e, se necessário, buscar acompanhamento profissional pode ser muito útil."
        elif frequencia == 'd' or frequencia == 'e': # Muito Frequentemente, Quase Sempre
            grupo = 4 # Grau 4: Indicação de suporte substancial
            mensagem = "Entendemos que esta é uma experiência frequente para você. Isso aponta para uma necessidade de suporte substancial. Recomendamos buscar orientação profissional para encontrar as melhores estratégias de manejo e apoio."
        else: # Caso algo inesperado aconteça com a frequência
            grupo = 5 # Grau 5: Erro ou classificação indefinida (pode ser usado para feedback)
            mensagem = "Houve um problema ao classificar sua frequência. Por favor, tente novamente ou entre em contato se o problema persistir."

    return grupo, mensagem

@app.route('/')
def home():
    return redirect(url_for('formulario'))

@app.route('/formulario', methods=['GET', 'POST'])
def formulario():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    perguntas_db = cursor.execute('SELECT id, enunciado, alternativa_a, alternativa_b, alternativa_c, alternativa_d FROM perguntas').fetchall()
    conn.close()

    if request.method == 'POST':
        conn_write = sqlite3.connect('database.db')
        cursor_write = conn_write.cursor()

        # Inserir um usuário genérico com campos vazios/nulos
        cursor_write.execute('INSERT INTO usuarios (nome, idade, email, pontuacao_total, grupo) VALUES (?, ?, ?, ?, ?)',
                       (None, None, None, 0, 0))
        usuario_id = cursor_write.lastrowid

        resposta_condicional = request.form.get('resposta_condicional')
        frequencia = request.form.get('frequencia')
        
        pergunta_historia_id = perguntas_db[0][0]

        # Definir a pontuação para a tabela de respostas (pode ser simbólica ou 0)
        ponto_para_resposta_db = 0
        resposta_para_db = resposta_condicional

        if resposta_condicional == 'sim':
            pontos_db_frequencia = {
                'a': 1, # Quase Nunca
                'b': 2, # Raramente
                'c': 3, # Ocasionalmente
                'd': 4, # Muito Frequentemente
                'e': 5  # Quase Sempre
            }
            ponto_para_resposta_db = pontos_db_frequencia.get(frequencia, 0)
            resposta_para_db = 'sim_' + frequencia

        cursor_write.execute('INSERT INTO respostas (usuario_id, pergunta_id, resposta, pontuacao) VALUES (?, ?, ?, ?)',
                           (usuario_id, pergunta_historia_id, resposta_para_db, ponto_para_resposta_db))
        
        grupo, mensagem_personalizada = classificar_usuario(resposta_condicional, frequencia)
        
        cursor_write.execute('UPDATE usuarios SET pontuacao_total=?, grupo=? WHERE id=?',
                       (0, grupo, usuario_id))
        
        conn_write.commit()
        conn_write.close()

        return redirect(url_for('resultado', grupo=grupo, mensagem=mensagem_personalizada))

    return render_template('formulario.html', perguntas=perguntas_db)

@app.route('/resultado')
def resultado():
    grupo = request.args.get('grupo')
    mensagem = request.args.get('mensagem')
    return render_template('resultado.html', grupo=grupo, mensagem=mensagem)

if __name__ == '__main__':
    app.run(debug=True, port=os.environ.get('PORT', 5001))