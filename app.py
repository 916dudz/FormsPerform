from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import shutil
import json
import os
from typing import Optional, List, Tuple
import sys
from werkzeug.serving import is_running_from_reloader
import tkinter as tk
from tkinter import simpledialog
from flask_mail import Mail, Message
from flask import abort
from dataclasses import dataclass
import logging

# number of trait questions (1..MAX_TRAITS inclusive)
MAX_TRAITS = 94

BASE_PATH = (
    getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    if getattr(sys, "frozen", False)
    else os.path.abspath(os.path.dirname(__file__))
)

BUNDLED_DB_PATH = os.path.join(BASE_PATH, "database.db")
USER_DATA_DIR = (
    os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), "AutSWOT")
    if sys.platform == "win32"
    else os.path.join(os.path.expanduser("~"), ".local", "share", "autswot")
)
PERSISTENT_DB_PATH = os.path.join(USER_DATA_DIR, "database.db")


def ensure_persistent_db() -> str:
    """Ensure the database is available in a persistent location."""
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    if not os.path.exists(PERSISTENT_DB_PATH) and os.path.exists(BUNDLED_DB_PATH):
        try:
            shutil.copy2(BUNDLED_DB_PATH, PERSISTENT_DB_PATH)
            logger.info(f"Copied bundled DB to: {PERSISTENT_DB_PATH}")
        except Exception as e:
            logger.error(f"Failed to copy bundled DB: {e}")
    return PERSISTENT_DB_PATH if getattr(sys, "frozen", False) else BUNDLED_DB_PATH

DB_PATH = ensure_persistent_db()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_PATH, "static"),
    template_folder=os.path.join(BASE_PATH, "templates"),
)

@dataclass
class Trait:
    score: float
    type: str
    name: str

@dataclass
class _TraitParseResult:
    index: int
    has_trait: bool
    freq: Optional[int] = None
    intensity: Optional[int] = None
    name: str = ""

# Initialize database schema
def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                swot_data TEXT NOT NULL,
                feedback TEXT
            )
        """)
        conn.commit()

def _parse_bool_field(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).lower() not in ("", "false", "0", "off", "none")

def _parse_trait_inputs(i: int, form) -> _TraitParseResult:

    #Parse request.form for trait i and return a small struct describing presence and numeric values.
    #Does not classify; only extracts and basic-validates inputs.

    has_trait = _parse_bool_field(form.get(f'condition_{i}'))
    name = trait_names[i] if i < len(trait_names) else f"Trait {i}"
    if not has_trait:
        return _TraitParseResult(index=i, has_trait=False, name=name)

    # questions 1-49 have intensity fields
    if 1 <= i <= 49:
        freq_val = form.get(f'frequency_{i}')
        intens_val = form.get(f'intensity_{i}')
        if freq_val is None or intens_val is None:
            # mark as error; the caller will convert to Trait(-1, "Erro", name)
            return _TraitParseResult(index=i, has_trait=True, freq=None, intensity=None, name=name)
        try:
            freq = int(freq_val)
            intensity = int(intens_val)
            return _TraitParseResult(index=i, has_trait=True, freq=freq, intensity=intensity, name=name)
        except Exception:
            return _TraitParseResult(index=i, has_trait=True, freq=None, intensity=None, name=name)
    else:
        # questions 50..93 have only frequency
        freq_val = form.get(f'frequency_{i}')
        if freq_val is None:
            return _TraitParseResult(index=i, has_trait=True, freq=None, intensity=None, name=name)
        try:
            freq = int(freq_val)
            return _TraitParseResult(index=i, has_trait=True, freq=freq, intensity=None, name=name)
        except Exception:
            return _TraitParseResult(index=i, has_trait=True, freq=None, intensity=None, name=name)

def _classify_with_intensity(i: int, average: float, thr: Optional[float], name: str) -> Trait:
    if i < 11:
        if thr is not None and average >= thr:
            return Trait(average, "Ameaça", name)
        elif average > 1.4:
            return Trait(average, "Fraqueza", name)
        else:
            return Trait(average, "Neutro", name)
    elif i < 26:
        if thr is not None and average >= thr:
            return Trait(average, "Ameaça", name)
        elif average > 1.4:
            return Trait(average, "Oportunidade", name)
        else:
            return Trait(average, "Neutro", name)
    else:
        if average > 3:
            return Trait(average, "Fraqueza", name)
        else:
            return Trait(average, "Oportunidade", name)

def _classify_without_intensity(freq: int, name: str) -> Trait:
    if freq in (1, 2):
        return Trait(freq, "Neutro", name)
    elif freq in (3, 4):
        return Trait(freq, "Força", name)
    else:
        return Trait(freq, "Oportunidade", name)



def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'contatoformsperform@gmail.com')

_mail_password_cache: Optional[str] = None

def get_mail_password() -> Optional[str]:
    global _mail_password_cache
    env_pw = os.environ.get("MAIL_PASSWORD")
    if env_pw:
        _mail_password_cache = env_pw
        return _mail_password_cache
    if is_running_from_reloader() and _mail_password_cache is not None:
        return _mail_password_cache
    try:
        root = tk.Tk()
        root.withdraw()
        password = simpledialog.askstring(
            "Senha do servidor E-mail",
            "Digite a senha do servidor E-mail da AutSWOT (deixe em branco para nunca mandar o email):",
            show="*"
        )
        root.destroy()
        _mail_password_cache = password
        return _mail_password_cache
    except Exception as e:
        logger.warning(f"Could not prompt for mail password: {e}")
        return None

app.config['MAIL_PASSWORD'] = get_mail_password()
mail = Mail(app)

with open(os.path.join(BASE_PATH, 'static', 'data', 'traits.json'), 'r', encoding='utf-8') as f:
    traits_data = json.load(f)

_raw_labels = traits_data.get('labels', [])
# Ensure 1-based indexing: trait_names[1] -> first question
if len(_raw_labels) == 0:
    trait_names = [''] * (MAX_TRAITS + 1)
else:
    # If the file already contains a placeholder at index 0 (rare), keep it.
    if _raw_labels[0].strip() == "":
        trait_names = _raw_labels[:]  # already has placeholder
    else:
        trait_names = [''] + _raw_labels[:]  # prepend placeholder

# Ensure minimum length MAX_TRAITS + 1 (index 0..MAX_TRAITS)
if len(trait_names) < (MAX_TRAITS + 1):
    trait_names += [f"Trait {i}" for i in range(len(trait_names), MAX_TRAITS + 1)]

_raw_thresholds = traits_data.get('thresholds', [])
thresholds = [None] + _raw_thresholds[:]  # make 1-based
if len(thresholds) < (MAX_TRAITS + 1):
    thresholds += [None] * ((MAX_TRAITS + 1) - len(thresholds))

@app.route("/")

@app.route("/intro")
def intro():
    return render_template("intro.html")

@app.route("/form")
def form():
    return render_template("form.html")

def formula() -> Tuple[int, List[Trait]]:
    # pre-create 94-length trait list (indices 0..93), index 0 unused
    traits: List[Trait] = [Trait(0.0, "", "") for _ in range(MAX_TRAITS+1)]

    form = request.form

    for i in range(1, MAX_TRAITS + 1):
        parsed = _parse_trait_inputs(i, form)
        if not parsed.has_trait:
            traits[i] = Trait(0.0, "Não possui o traço", parsed.name)
            continue

        if parsed.freq is None or (1 <= i <= 49 and parsed.intensity is None):
            logger.error("Campos de formulário ausentes/invalidos para a pergunta %d", i)
            traits[i] = Trait(-1, "Erro", parsed.name)
            continue

        if 1 <= i <= 49:
            # Pyright: ensure intensity is not Optional here
            assert parsed.intensity is not None
            intensity = parsed.intensity
            average = (parsed.freq + (intensity * 5.0 / 3.0)) / 2.0
            thr = thresholds[i] if i < len(thresholds) else None
            traits[i] = _classify_with_intensity(i, average, thr, parsed.name)
        else:
            traits[i] = _classify_without_intensity(parsed.freq, parsed.name)


    # prepare JSON-friendly swot_serializable (1..94)
    swot_serializable = [
        {
            "index": i,
            "score": float(traits[i].score),
            "category": traits[i].type,
            "name": traits[i].name,
        }
        for i in range(1, MAX_TRAITS + 1)
    ]

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO answer (swot_data) VALUES (?)",
            (json.dumps(swot_serializable, ensure_ascii=False),)
        )
        conn.commit()

        lid = cursor.lastrowid
        if lid is None:
            # fallback for sqlite: use last_insert_rowid()
            row = conn.execute("SELECT last_insert_rowid()").fetchone()
            lid = row[0] if row is not None else None

        if lid is None:
            raise RuntimeError("Could not determine last insert id")

    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

    return lid, traits


@app.route("/result", methods=["POST"])
def result():
    lid, traits = formula()
    return render_template(
        "result.html",
        traits=traits,
        feedback_id=lid
    )


@app.route('/feedback/<int:feedback_id>')
def feedback(feedback_id):
    return render_template('feedback.html', feedback_id=feedback_id)


@app.route('/save_feedback/<int:feedback_id>', methods=['POST'])
def save_feedback(feedback_id):
    feedback_json = json.dumps(request.form, ensure_ascii=False, indent=4)
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = 'UPDATE answer SET feedback = %s WHERE id = %s'
    placeholder = (feedback_json, feedback_id)
    if isinstance(conn, sqlite3.Connection):
        sql = sql.replace('%s', '?')
    cursor.execute(sql, placeholder)
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('email_page', feedback_id=feedback_id))


@app.route('/email_page/<int:feedback_id>')
def email_page(feedback_id):
    return render_template('email.html', feedback_id=feedback_id)


@app.route('/send_email/<int:feedback_id>', methods=['POST'])
def send_email(feedback_id):
    try:
        email_target = request.form.get('email')

        conn = get_db_connection()
        cursor = conn.cursor()
        sql = 'SELECT swot_data, feedback FROM answer WHERE id = %s'
        placeholder = (feedback_id,)
        if isinstance(conn, sqlite3.Connection):
            sql = sql.replace('%s', '?')
        cursor.execute(sql, placeholder)
        record = cursor.fetchone()
        logger.info("send_email: fetched record for id=%s: %s", feedback_id, "FOUND" if record else "NOT FOUND")
        cursor.close()
        conn.close()

        if record is None:
            abort(404, f"Feedback {feedback_id} não encontrado")

        swot_data = json.loads(record[0])
        feedback_data = json.loads(record[1]) if record[1] else {}

        if not email_target:
            abort(400, "Endereço de e-mail não fornecido")

        html_body = render_template(
            'email_template.html',
            swot=swot_data,
            feedback=feedback_data
        )

        # Build and send the message (previous code didn't call mail.send)
        msg = Message(
            subject="Seu Relatório Completo - AutSWOT",
            sender=("AutSWOT", app.config['MAIL_USERNAME']),
            recipients=[email_target],
            html=html_body
        )
        mail.send(msg)
        return redirect(url_for('confirmation'))
    except Exception:
        logger.exception("ERRO DE ENVIO DE E-MAIL")
        return "Ocorreu um erro ao enviar o e-mail.", 500


@app.route('/confirmation')
def confirmation():
    return render_template('confirmation.html')

if __name__ == "__main__":
    init_db()
    app.run(debug=False, use_reloader=False)
