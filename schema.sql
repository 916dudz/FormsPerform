CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    idade INTEGER NOT NULL,
    email TEXT,
    pontuacao_total INTEGER,
    grupo INTEGER
);

CREATE TABLE perguntas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enunciado TEXT,
    alternativa_a TEXT,
    alternativa_b TEXT,
    alternativa_c TEXT,
    alternativa_d TEXT,
    resposta_correta TEXT
);

CREATE TABLE respostas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    pergunta_id INTEGER,
    resposta TEXT,
    pontuacao INTEGER,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (pergunta_id) REFERENCES perguntas(id)
);