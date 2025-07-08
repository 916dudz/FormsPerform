from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

TRACOS = {
    str(i): {"min_freq": 3.0, "min_freq_int": 2.5} for i in range(1, 11)
}

INTENSIDADE_MAPA = {
    "vermelho": 3,
    "laranja": 2,
    "amarelo": 1,
    "nenhuma": 0
}

RECOMENDACOES_TRACO = {
    "1": "Promova atividades estruturadas que estimulem a previsibilidade e o conforto com mudanças leves.",
    "2": "Envolver-se em práticas de mindfulness e respiração pode ajudar a regular emoções intensas.",
    "3": "Trabalhe o desenvolvimento de habilidades sociais por meio de jogos simbólicos e dramatizações.",
    "4": "Crie uma rotina clara, com avisos prévios de mudanças para reduzir resistência e ansiedade.",
    "5": "Ofereça escolhas limitadas para promover senso de controle, minimizando rigidez comportamental.",
    "6": "Use reforço positivo e visual para apoiar a transição entre tarefas e ambientes.",
    "7": "Estimule a comunicação emocional por meio de histórias sociais e cartões de sentimento.",
    "8": "Aposte em mediação de conflitos e em escuta ativa para fomentar empatia e controle de impulsos.",
    "9": "Realize atividades que envolvam cooperação e resolução de problemas em grupo.",
    "10": "Explore jogos sensoriais que ajudem a modular estados de hiper ou hipo reatividade emocional."
}

POTENCIAIS_Oportunidades = {
    "1": True,
    "2": False,
    "3": True,
    "4": False,
    "5": True,
    "6": False,
    "7": True,
    "8": True,
    "9": False,
    "10": True
}

def classificar_traco(freq, intensidade, min_freq, min_freq_int, usar_intensidade=True):
    if usar_intensidade:
        intensidade_valor = INTENSIDADE_MAPA.get(intensidade.lower(), 0)
        intensidade_normalizada = intensidade_valor * (5 / 3)
        media = (freq + intensidade_normalizada) / 2
        return "T" if media >= min_freq_int else "W", media
    else:
        return "T" if freq >= min_freq else "W", freq

@app.route("/")
@app.route("/formulario")
def formulario():
    return render_template("formulario.html")

@app.route("/resultado", methods=["POST"])
def resultado():
    resultados = {}
    indicacoes = {}
    oportunidades = {}
    forcas = {}
    fraquezas = {}
    ameacas = {}
    pontuacao = 0
    usar_intensidade = True

    freq_map = {'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}

    for i in range(1, 11):
        cond = request.form.get(f"resposta_condicional_{i}")
        if cond != "sim":
            continue

        freq_letra = request.form.get(f"frequencia_{i}", "a")
        intensidade = request.form.get(f"intensidade_emocional_{i}", "nenhuma")
        freq = freq_map.get(freq_letra, 1)

        traco = TRACOS[str(i)]
        resultado, media = classificar_traco(freq, intensidade, traco["min_freq"], traco["min_freq_int"], usar_intensidade)
        resultados[str(i)] = resultado

        if resultado == "T":
            pontuacao += 1
            ameacas[str(i)] = RECOMENDACOES_TRACO.get(str(i), "Sem recomendação disponível para este traço.")
            if POTENCIAIS_Oportunidades.get(str(i), False):
                oportunidades[str(i)] = "Este traço pode se transformar em uma força com autoconhecimento ou intervenção especializada."
        else:
            fraquezas[str(i)] = "Traço com baixa intensidade que pode merecer atenção leve."
            if POTENCIAIS_Oportunidades.get(str(i), False):
                forcas[str(i)] = "Este traço representa uma força em seu perfil por sua estabilidade ou ausência de impacto negativo."

    return render_template("resultado.html",
                           pontuacao_total=pontuacao,
                           resultados=resultados,
                           tipo_calculo="Com intensidade emocional",
                           ameacas=ameacas,
                           fraquezas=fraquezas,
                           oportunidades=oportunidades,
                           forcas=forcas)

if __name__ == "__main__":
    app.run(debug=True)