import sqlite3
import os

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "tarifas.db")
)
# Garante que o diretório existe (necessário para volumes no Railway)
os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)

GRUPOS = ["GER", "EQT", "NEOENERGIA", "ENERGISA", "LIGHT", "CEMIG", "BRASILIA"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usina_id      TEXT NOT NULL,
    distribuidora TEXT NOT NULL,
    instalacao    TEXT NOT NULL UNIQUE,
    grupo         TEXT NOT NULL,
    desconto_base REAL NOT NULL,
    cobra_band    INTEGER NOT NULL DEFAULT 0,
    gd            INTEGER NOT NULL DEFAULT 1,
    tipo_gd       TEXT NOT NULL DEFAULT 'GD1',
    modalidade    TEXT NOT NULL DEFAULT 'Geração Compartilhada',
    obs           TEXT,
    criado_em     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS faturas (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id              INTEGER NOT NULL REFERENCES clientes(id),
    mes_referencia          TEXT NOT NULL,

    -- comuns a todos os grupos
    valor_concessionaria    REAL,
    consumo_kwh             REAL NOT NULL,
    injetada_kwh            REAL NOT NULL,
    desconto_base           REAL NOT NULL,
    desconto_aplicado       REAL,
    cobra_band              INTEGER NOT NULL DEFAULT 0,

    -- GER: TE + TUSD separados
    te_consumo              REAL,
    tusd_consumo            REAL,
    te_compensada           REAL,
    tusd_compensada         REAL,

    -- NEOENERGIA: TUSD + TE com nomes próprios
    tusd_distribuidora      REAL,
    te_distribuidora        REAL,
    desconto_injecao        REAL,

    -- EQT / CEMIG / BRASILIA / ENERGISA / LIGHT: tarifa direta
    tarifa_distribuidora_input REAL,
    tarifa_compensada_input    REAL,
    ajuste_gd2              REAL,

    -- EQT: SCEE (5 campos)
    scee_consumo            REAL,
    scee_injecao            REAL,
    scee_comp_nao_isento    REAL,
    scee_beneficio_bruto    REAL,
    scee_beneficio_liquido  REAL,

    -- LIGHT: TUSD/TE da injeção e fornecimento
    tusd_injetada_gd        REAL,
    te_injetada_gd          REAL,
    tusd_fornecida_gd       REAL,
    te_fornecida_gd         REAL,

    -- LIGHT: impostos (necessários para calcular valor_geracao)
    aliquota_icms           REAL,
    valor_icms              REAL,
    aliquota_pis            REAL,
    valor_pis               REAL,
    aliquota_cofins         REAL,
    valor_cofins            REAL,

    -- Bandeira consumo: todos os grupos têm pelo menos os valores
    b_amarela_cons_kwh      REAL DEFAULT 0,
    b_amarela_cons_valor    REAL DEFAULT 0,
    b_verm_p1_cons_kwh      REAL DEFAULT 0,
    b_verm_p1_cons_valor    REAL DEFAULT 0,
    b_verm_p2_cons_kwh      REAL DEFAULT 0,
    b_verm_p2_cons_valor    REAL DEFAULT 0,

    -- Bandeira injeção: apenas GER, EQT, CEMIG
    b_amarela_inj_kwh       REAL DEFAULT 0,
    b_amarela_inj_valor     REAL DEFAULT 0,
    b_verm_p1_inj_kwh       REAL DEFAULT 0,
    b_verm_p1_inj_valor     REAL DEFAULT 0,
    b_verm_p2_inj_kwh       REAL DEFAULT 0,
    b_verm_p2_inj_valor     REAL DEFAULT 0,

    -- Outputs calculados
    tarifa_distribuidora    REAL,
    tarifa_compensada       REAL,
    tarifa_geracao          REAL,
    desconto_real           REAL,
    desconto_ref            REAL,

    -- Pagamento
    status_pagamento        TEXT DEFAULT 'pendente',
    data_pagamento          DATE,
    obs                     TEXT,
    criado_em               DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(cliente_id, mes_referencia)
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_DESCONTOS_PADRAO = [
    ("Amazonas Energia",        "AM",  0.05),
    ("Equatorial CEA",          "AP",  0.05),
    ("Equatorial CEEE",         "RS",  0.10),
    ("CEGERO",                  "SC",  0.10),
    ("CELETRO",                 "RS",  0.10),
    ("CERCI",                   "RJ",  0.12),
    ("CERFOX",                  "RS",  0.10),
    ("CERMC",                   "SP",  0.10),
    ("CERRP",                   "SP",  0.10),
    ("CERTHIL",                 "RS",  0.10),
    ("CERVAM",                  "SP",  0.15),
    ("COOPERNORTE",             "RS",  0.10),
    ("COOPERSUL",               "RS",  0.10),
    ("COOPERZEM",               "SC",  0.10),
    ("COPREL",                  "RS",  0.10),
    ("CPFL Paulista",           "SP",  0.10),
    ("CPFL Piratininga",        "SP",  0.10),
    ("CPFL Santa Cruz",         "SP",  0.05),
    ("Castro - DIS",            "PR",  0.10),
    ("Cedrap",                  "SP",  0.15),
    ("Cedri",                   "SP",  0.15),
    ("Cejama",                  "SC",  0.10),
    ("Celesc-DIS",              "SC",  0.10),
    ("Celesc-DIS",              "PR",  0.10),
    ("Cemig-D",                 "MG",  0.20),
    ("Cemirim",                 "SP",  0.15),
    ("Ceprag",                  "SC",  0.10),
    ("Ceral Anitápolis",        "SC",  0.10),
    ("Ceral Araruama",          "RJ",  0.12),
    ("Ceral DIS",               "PR",  0.10),
    ("Ceraça",                  "SC",  0.10),
    ("Cerbranorte",             "SC",  0.10),
    ("Cercos",                  "SE",  0.05),
    ("Cerej",                   "SC",  0.10),
    ("Ceres",                   "RJ",  0.12),
    ("Cergal",                  "SC",  0.10),
    ("Cergapa",                 "SC",  0.10),
    ("Cergral",                 "SC",  0.10),
    ("Ceriluz",                 "RS",  0.10),
    ("Cerim",                   "SP",  0.10),
    ("Ceripa",                  "SP",  0.05),
    ("Ceris",                   "SP",  0.05),
    ("Cermissões",              "RS",  0.10),
    ("Cermoful",                "SC",  0.10),
    ("Cernhe",                  "SP",  0.05),
    ("Cerpalo",                 "SC",  0.10),
    ("Cerpro",                  "SP",  0.10),
    ("Cersad",                  "SC",  0.10),
    ("Cersul",                  "SC",  0.10),
    ("Certaja",                 "RS",  0.10),
    ("Certel",                  "RS",  0.10),
    ("Certrel",                 "SC",  0.10),
    ("Cetril",                  "SP",  0.10),
    ("Chesp",                   "GO",  0.05),
    ("Cocel",                   "PR",  0.10),
    ("Codesam",                 "SC",  0.10),
    ("Coopera",                 "SC",  0.10),
    ("Cooperaliança",           "SC",  0.10),
    ("Coopercocal",             "SC",  0.10),
    ("Cooperluz",               "RS",  0.10),
    ("Coopermila",              "SC",  0.10),
    ("Coorsel",                 "SC",  0.10),
    ("Copel-DIS",               "PR",  0.10),
    ("Creluz-D",                "RS",  0.10),
    ("Creral",                  "RS",  0.10),
    ("DMED",                    "MG",  0.05),
    ("Dcelt",                   "SC",  0.10),
    ("Demei",                   "RS",  0.10),
    ("EDP ES",                  "ES",  0.05),
    ("EDP SP",                  "SP",  0.10),
    ("EFLJC",                   "SC",  0.10),
    ("ELFSM",                   "ES",  0.05),
    ("Energisa Sul Sudeste",    "SP",  0.05),
    ("Eflul",                   "SC",  0.10),
    ("Eletrocar",               "RS",  0.10),
    ("Enel CE",                 "CE",  0.10),
    ("Enel GO",                 "GO",  0.10),
    ("Equatorial GO",           "GO",  0.12),
    ("Enel RJ",                 "RJ",  0.10),
    ("Enel SP",                 "SP",  0.05),
    ("Energisa AC",             "AC",  0.05),
    ("Energisa Borborema",      "PB",  0.05),
    ("Energisa Minas Rio",      "MG",  0.05),
    ("Energisa MS",             "MS",  0.14),
    ("Energisa MT",             "MT",  0.14),
    ("Energisa Nova Friburgo",  "RJ",  0.05),
    ("Energisa PB",             "PB",  0.05),
    ("Energisa RO",             "RO",  0.05),
    ("Energisa SE",             "SE",  0.05),
    ("Energisa TO",             "TO",  0.10),
    ("Equatorial AL",           "AL",  0.10),
    ("Equatorial MA",           "MA",  0.10),
    ("Equatorial PA",           "PA",  0.10),
    ("Equatorial PI",           "PI",  0.10),
    ("Forcel",                  "PR",  0.10),
    ("Hidropan",                "RS",  0.10),
    ("Light",                   "RJ",  0.05),
    ("MuxEnergia",              "RS",  0.10),
    ("Neoenergia Brasília",     "DF",  0.10),
    ("Neoenergia Coelba",       "BA",  0.12),
    ("Neoenergia Cosern",       "RN",  0.10),
    ("Neoenergia Elektro",      "SP",  0.15),
    ("Neoenergia Pernambuco",   "PE",  0.12),
    ("Nova Palma",              "RS",  0.10),
    ("RGE",                     "RS",  0.10),
    ("Roraima Energia",         "RR",  0.05),
    ("Sulgipe",                 "SE",  0.05),
]


def init_descontos_padrao():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS descontos_padrao (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                distribuidora TEXT NOT NULL,
                estado        TEXT,
                desconto      REAL NOT NULL,
                UNIQUE(distribuidora, estado)
            )
        """)
        conn.executemany("""
            INSERT INTO descontos_padrao (distribuidora, estado, desconto)
            VALUES (?, ?, ?)
            ON CONFLICT(distribuidora, estado) DO UPDATE SET desconto=excluded.desconto
        """, _DESCONTOS_PADRAO)


def get_desconto_padrao(distribuidora):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT AVG(desconto) as desconto FROM descontos_padrao WHERE distribuidora = ?",
            (distribuidora,)
        ).fetchone()
        return row["desconto"] if row and row["desconto"] is not None else None


def init_db():
    from concessionarias import normalizar_distribuidora
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        init_descontos_padrao()
        for col, defn in [
            ("tipo_gd",    "TEXT NOT NULL DEFAULT 'GD1'"),
            ("modalidade", "TEXT NOT NULL DEFAULT 'Geração Compartilhada'"),
        ]:
            try:
                conn.execute(f"ALTER TABLE clientes ADD COLUMN {col} {defn}")
            except Exception:
                pass
        # Normaliza nomes longos de distribuidora para nome curto da lista
        rows = conn.execute("SELECT id, distribuidora FROM clientes").fetchall()
        for row in rows:
            curto = normalizar_distribuidora(row["distribuidora"])
            if curto != row["distribuidora"]:
                conn.execute("UPDATE clientes SET distribuidora=? WHERE id=?",
                             (curto, row["id"]))


def get_clientes():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM clientes ORDER BY grupo, distribuidora, instalacao"
        ).fetchall()


def get_cliente(id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM clientes WHERE id=?", (id,)).fetchone()


def salvar_cliente(data, id=None):
    cols = ["usina_id","distribuidora","instalacao","grupo","desconto_base","cobra_band","gd","tipo_gd","modalidade","obs"]
    vals = [data.get(c) for c in cols]
    with get_conn() as conn:
        if id:
            conn.execute(f"UPDATE clientes SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?", vals + [id])
        else:
            cur = conn.execute(f"INSERT INTO clientes ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", vals)
            return cur.lastrowid


def get_faturas_mes(mes):
    with get_conn() as conn:
        return conn.execute("""
            SELECT f.*, c.usina_id, c.distribuidora, c.instalacao, c.grupo, c.tipo_gd, c.modalidade
            FROM faturas f JOIN clientes c ON c.id=f.cliente_id
            WHERE f.mes_referencia=?
            ORDER BY f.criado_em DESC
        """, (mes,)).fetchall()


def get_faturas_cliente(cliente_id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT f.*, c.usina_id, c.distribuidora, c.instalacao, c.grupo, c.tipo_gd, c.modalidade
            FROM faturas f JOIN clientes c ON c.id=f.cliente_id
            WHERE f.cliente_id=?
            ORDER BY f.mes_referencia DESC
        """, (cliente_id,)).fetchall()


def get_fatura_por_cliente_mes(cliente_id, mes_referencia):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM faturas WHERE cliente_id=? AND mes_referencia=?",
            (cliente_id, mes_referencia)
        ).fetchone()


def get_fatura(id):
    with get_conn() as conn:
        return conn.execute("""
            SELECT f.*, c.usina_id, c.distribuidora, c.instalacao, c.grupo,
                   c.tipo_gd, c.modalidade,
                   c.desconto_base as cliente_desconto_base,
                   c.cobra_band as cliente_cobra_band
            FROM faturas f JOIN clientes c ON c.id=f.cliente_id
            WHERE f.id=?
        """, (id,)).fetchone()


# Todas as colunas de entrada que podem vir do formulário
_INPUT_COLS = [
    "cliente_id","mes_referencia","valor_concessionaria",
    "consumo_kwh","injetada_kwh","desconto_base","desconto_aplicado","cobra_band",
    "te_consumo","tusd_consumo","te_compensada","tusd_compensada",
    "tusd_distribuidora","te_distribuidora","desconto_injecao",
    "tarifa_distribuidora_input","tarifa_compensada_input","ajuste_gd2",
    "scee_consumo","scee_injecao","scee_comp_nao_isento",
    "scee_beneficio_bruto","scee_beneficio_liquido",
    "tusd_injetada_gd","te_injetada_gd","tusd_fornecida_gd","te_fornecida_gd",
    "aliquota_icms","valor_icms","aliquota_pis","valor_pis","aliquota_cofins","valor_cofins",
    "b_amarela_cons_kwh","b_amarela_cons_valor",
    "b_verm_p1_cons_kwh","b_verm_p1_cons_valor",
    "b_verm_p2_cons_kwh","b_verm_p2_cons_valor",
    "b_amarela_inj_kwh","b_amarela_inj_valor",
    "b_verm_p1_inj_kwh","b_verm_p1_inj_valor",
    "b_verm_p2_inj_kwh","b_verm_p2_inj_valor",
    "tarifa_distribuidora","tarifa_compensada","tarifa_geracao","desconto_real","desconto_ref",
    "status_pagamento","data_pagamento","obs",
]


def salvar_fatura(data, id=None):
    cols = [c for c in _INPUT_COLS if c != "cliente_id" or not id]
    if id:
        cols = [c for c in _INPUT_COLS if c not in ("cliente_id",)]
    vals = [data.get(c) for c in cols]
    with get_conn() as conn:
        if id:
            sets = ", ".join(f"{c}=?" for c in cols)
            conn.execute(f"UPDATE faturas SET {sets} WHERE id=?", vals + [id])
            return id
        else:
            all_cols = _INPUT_COLS
            all_vals = [data.get(c) for c in all_cols]
            cur = conn.execute(
                f"INSERT INTO faturas ({','.join(all_cols)}) VALUES ({','.join(['?']*len(all_cols))})",
                all_vals
            )
            return cur.lastrowid


def get_meses_disponiveis():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT mes_referencia FROM faturas ORDER BY mes_referencia DESC"
        ).fetchall()
        return [r["mes_referencia"] for r in rows]


def deletar_fatura(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM faturas WHERE id=?", (id,))


def deletar_cliente(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM faturas WHERE cliente_id=?", (id,))
        conn.execute("DELETE FROM clientes WHERE id=?", (id,))


def init_tarifas_gerador():
    """Cria tabela tarifas_gerador se não existir."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tarifas_gerador (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                distribuidora       TEXT NOT NULL,
                mes_referencia      TEXT NOT NULL,
                tipo_gd             TEXT,
                modalidade          TEXT,
                desconto_gd         REAL,
                tarifa_compensada   REAL,
                tarifa_distribuidora REAL,
                tarifa_geracao      REAL,
                desagio             REAL,
                t_gerador           REAL,
                criado_em           DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(distribuidora, mes_referencia, tipo_gd, modalidade)
            )
        """)


def salvar_tarifa_gerador(data):
    cols = ["distribuidora","mes_referencia","tipo_gd","modalidade",
            "desconto_gd","tarifa_compensada","tarifa_distribuidora","tarifa_geracao","desagio","t_gerador"]
    vals = [data.get(c) for c in cols]
    with get_conn() as conn:
        # Garantir coluna existe (migração)
        try:
            conn.execute("ALTER TABLE tarifas_gerador ADD COLUMN tarifa_geracao REAL")
        except Exception:
            pass
        conn.execute(f"""
            INSERT INTO tarifas_gerador ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})
            ON CONFLICT(distribuidora, mes_referencia, tipo_gd, modalidade)
            DO UPDATE SET
                desconto_gd=excluded.desconto_gd,
                tarifa_compensada=excluded.tarifa_compensada,
                tarifa_distribuidora=excluded.tarifa_distribuidora,
                tarifa_geracao=excluded.tarifa_geracao,
                desagio=excluded.desagio,
                t_gerador=excluded.t_gerador,
                criado_em=CURRENT_TIMESTAMP
        """, vals)


def get_tarifas_gerador(distribuidora=None, mes=None):
    with get_conn() as conn:
        cond, params = [], []
        if distribuidora:
            cond.append("distribuidora = ?"); params.append(distribuidora)
        if mes:
            cond.append("mes_referencia = ?"); params.append(mes[:7] + "-01")
        where = ("WHERE " + " AND ".join(cond)) if cond else ""
        return conn.execute(
            f"SELECT * FROM tarifas_gerador {where} ORDER BY criado_em DESC",
            params
        ).fetchall()


def deletar_tarifa_gerador(id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tarifas_gerador WHERE id=?", (id,))


def get_todas_faturas():
    with get_conn() as conn:
        return conn.execute("""
            SELECT f.*, c.usina_id, c.distribuidora, c.instalacao, c.grupo, c.tipo_gd, c.modalidade
            FROM faturas f JOIN clientes c ON c.id=f.cliente_id
            ORDER BY f.mes_referencia DESC, c.grupo, c.distribuidora, c.instalacao
        """).fetchall()


def get_distribuidoras():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT distribuidora FROM clientes ORDER BY distribuidora"
        ).fetchall()
        return [r["distribuidora"] for r in rows]
