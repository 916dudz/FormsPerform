from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import json
import os
import psycopg
from flask_mail import Mail, Message
from flask import abort

app = Flask(__name__)

# --- CONFIGURAÇÃO DO BANCO DE DADOS E E-MAIL ---
def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return psycopg.connect(db_url)
    else:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        return conn

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = "contatoformsperform@gmail.com"
app.config['MAIL_PASSWORD'] = "uttzhrvdhwzcfrhj" # Sua senha de app de 16 letras

mail = Mail(app)

# --- DICIONÁRIOS DE REGRAS (coloque as suas regras aqui) ---
INTENSIDADE_MAPA = {"vermelho": 3, "laranja": 2, "amarelo": 1, "nenhuma": 0}
freq_map = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
TRACOS = {str(i): {"min_freq": 3.0, "min_freq_int": 2.5} for i in range(1, 96)}
RECOMENDACOES_TRACO = {str(i): f"Recomendação para o traço {i}" for i in range(1, 96)}
POTENCIAIS_Oportunidades = {str(i): False for i in range(1, 96)}

def classificar_traco(freq, intensidade, min_freq, min_freq_int):
    intensidade_valor = INTENSIDADE_MAPA.get(intensidade.lower(), 0)
    intensidade_normalizada = intensidade_valor * (5 / 3)
    media = (freq + intensidade_normalizada) / 2
    return "T" if media >= min_freq_int else "W", media

@app.route("/")
@app.route("/formulario")
def formulario():
    return render_template("formulario.html")

@app.route("/resultado", methods=["POST"])
def resultado():
    # Calcular SWOT a partir do request.form
    forcas = {}
    fraquezas = {}
    ameacas = {}
    oportunidades = {}

    # Loop para processar os traços de 1 a 95
    for i in range(1, 96):
        freq_key = f'freq_{i}'
        intensidade_key = f'intensidade_{i}'

        if freq_key in request.form and intensidade_key in request.form:
            freq_value = request.form[freq_key]
            intensidade_value = request.form[intensidade_key]

            # Converter frequência para valor numérico
            freq = freq_map.get(freq_value, 0)

            # Obter parâmetros do traço
            traco_params = TRACOS.get(str(i), {"min_freq": 3.0, "min_freq_int": 2.5})

            # Classificar o traço
            classificacao, media = classificar_traco(
                freq, intensidade_value,
                traco_params["min_freq"],
                traco_params["min_freq_int"]
            )

            recomendacao = RECOMENDACOES_TRACO.get(str(i), f"Recomendação para o traço {i}")
            eh_oportunidade = POTENCIAIS_Oportunidades.get(str(i), False)

            traco_data = {
                "frequencia": freq_value,
                "intensidade": intensidade_value,
                "media": round(media, 2),
                "recomendacao": recomendacao
            }

            if classificacao == "T":
                if eh_oportunidade:
                    oportunidades[str(i)] = traco_data
                else:
                    forcas[str(i)] = traco_data
            else:  # classificacao == "W"
                if eh_oportunidade:
                    ameacas[str(i)] = traco_data
                else:
                    fraquezas[str(i)] = traco_data

    swot_data_json = json.dumps({'forcas': forcas, 'fraquezas': fraquezas, 'ameacas': ameacas, 'oportunidades': oportunidades})

    conn = get_db_connection()
    cursor = conn.cursor()

    if isinstance(conn, sqlite3.Connection):
        sql = 'INSERT INTO feedback (resposta_discursiva, swot_data) VALUES (?, ?) RETURNING id'
        params = ('', swot_data_json)
    else:
        sql = 'INSERT INTO feedback (resposta_discursiva, swot_data) VALUES (%s, %s) RETURNING id'
        params = ('', swot_data_json)

    cursor.execute(sql, params)
    row = cursor.fetchone()
    if not row:
        conn.rollback()
        abort(500, "Não foi possível obter o ID do feedback inserido")
    feedback_id = row[0]

    conn.commit()
    cursor.close()
    conn.close()

    return render_template("resultado.html",
                        feedback_id=feedback_id,
                        forcas=forcas,
                        fraquezas=fraquezas,
                        ameacas=ameacas,
                        oportunidades=oportunidades)

@app.route('/pagina_discursiva/<int:feedback_id>')
def pagina_discursiva(feedback_id):
    return render_template('discursivas.html', feedback_id=feedback_id)

@app.route('/salvar_discursiva/<int:feedback_id>', methods=['POST'])
def salvar_discursiva(feedback_id):
    respostas_discursivas_json = json.dumps(request.form, ensure_ascii=False, indent=4)
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = 'UPDATE feedback SET resposta_discursiva = %s WHERE id = %s'
    placeholder = (respostas_discursivas_json, feedback_id)
    if isinstance(conn, sqlite3.Connection):
        sql = sql.replace('%s', '?')
    cursor.execute(sql, placeholder)
    conn.commit()
    cursor.close()
    conn.close()
    # Redireciona para a nova página de e-mail
    return redirect(url_for('pagina_email', feedback_id=feedback_id))

# NOVA ROTA PARA A PÁGINA DE E-MAIL
@app.route('/pagina_email/<int:feedback_id>')
def pagina_email(feedback_id):
    return render_template('email.html', feedback_id=feedback_id)

@app.route('/enviar_email/<int:feedback_id>', methods=['POST'])
def enviar_email(feedback_id):
    try:
        email_destinatario = request.form.get('email')

        # Busca os dados completos (SWOT + Discursivas) do banco
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = 'SELECT swot_data, resposta_discursiva FROM feedback WHERE id = %s'
        placeholder = (feedback_id,)
        if isinstance(conn, sqlite3.Connection):
            sql = sql.replace('%s', '?')
        cursor.execute(sql, placeholder)
        record = cursor.fetchone()
        conn.close()

        if record is None:
            # no such feedback → 404
            abort(404, f"Feedback {feedback_id} não encontrado")

        # now safe to subsript
        swot_data = json.loads(record[0])
        discursiva_data = json.loads(record[1])

        if not email_destinatario:
            abort(400, "Endereço de e‑mail não fornecido")

        html_body = render_template(
            'email_template.html',
            swot=swot_data,
            discursivas=discursiva_data
        )
        Message(
            subject="Seu Relatório Completo - FormsPerform",
            sender=("FormsPerform", app.config['MAIL_USERNAME']),
            # now guaranteed to be a str, not None
            recipients=[email_destinatario],
            html=html_body
        )
        return redirect(url_for('confirmacao'))
    except Exception as e:
        print(f"ERRO DE ENVIO DE E-MAIL: {e}")
        return "Ocorreu um erro ao enviar o e-mail.", 500

@app.route('/confirmacao')
def confirmacao():
    return render_template('confirmacao.html')

if __name__ == "__main__":
    app.run(debug=True)
