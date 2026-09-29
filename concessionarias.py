import re

CONCESSIONARIAS = [
    {"nome": "Amazonas Energia",          "estado": "AM", "desconto": 0.05},
    {"nome": "Equatorial CEA",            "estado": "AP", "desconto": 0.05},
    {"nome": "Equatorial CEEE",           "estado": "RS", "desconto": 0.10},
    {"nome": "CEGERO",                    "estado": "SC", "desconto": 0.10},
    {"nome": "CELETRO",                   "estado": "RS", "desconto": 0.10},
    {"nome": "CERCI",                     "estado": "RJ", "desconto": 0.12},
    {"nome": "CERFOX",                    "estado": "RS", "desconto": 0.10},
    {"nome": "CERMC",                     "estado": "SP", "desconto": 0.10},
    {"nome": "CERRP",                     "estado": "SP", "desconto": 0.10},
    {"nome": "CERTHIL",                   "estado": "RS", "desconto": 0.10},
    {"nome": "CERVAM",                    "estado": "SP", "desconto": 0.15},
    {"nome": "COOPERNORTE",               "estado": "RS", "desconto": 0.10},
    {"nome": "COOPERSUL",                 "estado": "RS", "desconto": 0.10},
    {"nome": "COOPERZEM",                 "estado": "SC", "desconto": 0.10},
    {"nome": "COPREL",                    "estado": "RS", "desconto": 0.10},
    {"nome": "CPFL Paulista",             "estado": "SP", "desconto": 0.10},
    {"nome": "CPFL Piratininga",          "estado": "SP", "desconto": 0.10},
    {"nome": "CPFL Santa Cruz",           "estado": "SP", "desconto": 0.05},
    {"nome": "Castro - DIS",              "estado": "PR", "desconto": 0.10},
    {"nome": "Cedrap",                    "estado": "SP", "desconto": 0.15},
    {"nome": "Cedri",                     "estado": "SP", "desconto": 0.15},
    {"nome": "Cejama",                    "estado": "SC", "desconto": 0.10},
    {"nome": "Celesc-DIS",                "estado": "SC", "desconto": 0.10},
    {"nome": "Celesc-DIS",                "estado": "PR", "desconto": 0.10},
    {"nome": "Cemig-D",                   "estado": "MG", "desconto": 0.20},
    {"nome": "Cemirim",                   "estado": "SP", "desconto": 0.15},
    {"nome": "Ceprag",                    "estado": "SC", "desconto": 0.10},
    {"nome": "Ceral Anitápolis",          "estado": "SC", "desconto": 0.10},
    {"nome": "Ceral Araruama",            "estado": "RJ", "desconto": 0.12},
    {"nome": "Ceral DIS",                 "estado": "PR", "desconto": 0.10},
    {"nome": "Ceraça",                    "estado": "SC", "desconto": 0.10},
    {"nome": "Cerbranorte",               "estado": "SC", "desconto": 0.10},
    {"nome": "Cercos",                    "estado": "SE", "desconto": 0.05},
    {"nome": "Cerej",                     "estado": "SC", "desconto": 0.10},
    {"nome": "Ceres",                     "estado": "RJ", "desconto": 0.12},
    {"nome": "Cergal",                    "estado": "SC", "desconto": 0.10},
    {"nome": "Cergapa",                   "estado": "SC", "desconto": 0.10},
    {"nome": "Cergral",                   "estado": "SC", "desconto": 0.10},
    {"nome": "Ceriluz",                   "estado": "RS", "desconto": 0.10},
    {"nome": "Cerim",                     "estado": "SP", "desconto": 0.10},
    {"nome": "Ceripa",                    "estado": "SP", "desconto": 0.05},
    {"nome": "Ceris",                     "estado": "SP", "desconto": 0.05},
    {"nome": "Cermissões",                "estado": "RS", "desconto": 0.10},
    {"nome": "Cermoful",                  "estado": "SC", "desconto": 0.10},
    {"nome": "Cernhe",                    "estado": "SP", "desconto": 0.05},
    {"nome": "Cerpalo",                   "estado": "SC", "desconto": 0.10},
    {"nome": "Cerpro",                    "estado": "SP", "desconto": 0.10},
    {"nome": "Cersad",                    "estado": "SC", "desconto": 0.10},
    {"nome": "Cersul",                    "estado": "SC", "desconto": 0.10},
    {"nome": "Certaja",                   "estado": "RS", "desconto": 0.10},
    {"nome": "Certel",                    "estado": "RS", "desconto": 0.10},
    {"nome": "Certrel",                   "estado": "SC", "desconto": 0.10},
    {"nome": "Cetril",                    "estado": "SP", "desconto": 0.10},
    {"nome": "Chesp",                     "estado": "GO", "desconto": 0.05},
    {"nome": "Cocel",                     "estado": "PR", "desconto": 0.10},
    {"nome": "Codesam",                   "estado": "SC", "desconto": 0.10},
    {"nome": "Coopera",                   "estado": "SC", "desconto": 0.10},
    {"nome": "Cooperaliança",             "estado": "SC", "desconto": 0.10},
    {"nome": "Coopercocal",               "estado": "SC", "desconto": 0.10},
    {"nome": "Cooperluz",                 "estado": "RS", "desconto": 0.10},
    {"nome": "Coopermila",                "estado": "SC", "desconto": 0.10},
    {"nome": "Coorsel",                   "estado": "SC", "desconto": 0.10},
    {"nome": "Copel-DIS",                 "estado": "PR", "desconto": 0.10},
    {"nome": "Creluz-D",                  "estado": "RS", "desconto": 0.10},
    {"nome": "Creral",                    "estado": "RS", "desconto": 0.10},
    {"nome": "DMED",                      "estado": "MG", "desconto": 0.05},
    {"nome": "Dcelt",                     "estado": "SC", "desconto": 0.10},
    {"nome": "Demei",                     "estado": "RS", "desconto": 0.10},
    {"nome": "EDP ES",                    "estado": "ES", "desconto": 0.05},
    {"nome": "EDP SP",                    "estado": "SP", "desconto": 0.10},
    {"nome": "EFLJC",                     "estado": "SC", "desconto": 0.10},
    {"nome": "ELFSM",                     "estado": "ES", "desconto": 0.05},
    {"nome": "Energisa Sul Sudeste",      "estado": "SP", "desconto": 0.05},
    {"nome": "Eflul",                     "estado": "SC", "desconto": 0.10},
    {"nome": "Eletrocar",                 "estado": "RS", "desconto": 0.10},
    {"nome": "Enel CE",                   "estado": "CE", "desconto": 0.10},
    {"nome": "Enel GO",                   "estado": "GO", "desconto": 0.10},
    {"nome": "Equatorial GO",             "estado": "GO", "desconto": 0.12},
    {"nome": "Enel RJ",                   "estado": "RJ", "desconto": 0.10},
    {"nome": "Enel SP",                   "estado": "SP", "desconto": 0.05},
    {"nome": "Energisa AC",               "estado": "AC", "desconto": 0.05},
    {"nome": "Energisa Borborema",        "estado": "PB", "desconto": 0.05},
    {"nome": "Energisa Minas Rio",        "estado": "MG", "desconto": 0.05},
    {"nome": "Energisa MS",               "estado": "MS", "desconto": 0.14},
    {"nome": "Energisa MT",               "estado": "MT", "desconto": 0.14},
    {"nome": "Energisa Nova Friburgo",    "estado": "RJ", "desconto": 0.05},
    {"nome": "Energisa PB",               "estado": "PB", "desconto": 0.05},
    {"nome": "Energisa RO",               "estado": "RO", "desconto": 0.05},
    {"nome": "Energisa SE",               "estado": "SE", "desconto": 0.05},
    {"nome": "Energisa TO",               "estado": "TO", "desconto": 0.10},
    {"nome": "Equatorial AL",             "estado": "AL", "desconto": 0.10},
    {"nome": "Equatorial MA",             "estado": "MA", "desconto": 0.10},
    {"nome": "Equatorial PA",             "estado": "PA", "desconto": 0.10},
    {"nome": "Equatorial PI",             "estado": "PI", "desconto": 0.10},
    {"nome": "Forcel",                    "estado": "PR", "desconto": 0.10},
    {"nome": "Hidropan",                  "estado": "RS", "desconto": 0.10},
    {"nome": "Light",                     "estado": "RJ", "desconto": 0.05},
    {"nome": "MuxEnergia",                "estado": "RS", "desconto": 0.10},
    {"nome": "Neoenergia Brasília",       "estado": "DF", "desconto": 0.10},
    {"nome": "Neoenergia Coelba",         "estado": "BA", "desconto": 0.12},
    {"nome": "Neoenergia Cosern",         "estado": "RN", "desconto": 0.10},
    {"nome": "Neoenergia Elektro",        "estado": "SP", "desconto": 0.15},
    {"nome": "Neoenergia Pernambuco",     "estado": "PE", "desconto": 0.12},
    {"nome": "Nova Palma",                "estado": "RS", "desconto": 0.10},
    {"nome": "RGE",                       "estado": "RS", "desconto": 0.10},
    {"nome": "Roraima Energia",           "estado": "RR", "desconto": 0.05},
    {"nome": "Sulgipe",                   "estado": "SE", "desconto": 0.05},
]

# índice por nome para lookup rápido
CONC_POR_NOME = {c["nome"]: c for c in CONCESSIONARIAS}

# ── Normalização: converte nome oficial do PDF para nome curto da lista ────────

# Aliases: palavras-chave únicas que identificam cada concessionária
# quando o nome extraído pelo Claude é diferente do nome da lista
_ALIASES = {
    "COSERN":           "Neoenergia Cosern",
    "COELBA":           "Neoenergia Coelba",
    "CELPE":            "Neoenergia Pernambuco",
    "ELEKTRO":          "Neoenergia Elektro",
    "CEB-DIS":          "Neoenergia Brasília",
    "CEB DISTRIBUIÇÃO": "Neoenergia Brasília",
    "COPEL":            "Copel-DIS",
    "CELESC":           "Celesc-DIS",
    "CEMIG":            "Cemig-D",
    "LIGHT":            "Light",
    "RGE SUL":          "RGE",   # RGE SUL DISTRIBUIDORA é sempre a RGE (RS)
    "EQUATORIAL ALAGOAS":   "Equatorial AL",
    "EQUATORIAL MARANHÃO":  "Equatorial MA",
    "EQUATORIAL MARANHAO":  "Equatorial MA",
    "EQUATORIAL PARÁ":      "Equatorial PA",
    "EQUATORIAL PARA":      "Equatorial PA",
    "EQUATORIAL PIAUÍ":     "Equatorial PI",
    "EQUATORIAL PIAUI":     "Equatorial PI",
    "EQUATORIAL GOIÁS":     "Equatorial GO",
    "EQUATORIAL GOIAS":     "Equatorial GO",
    "ENEL CEARÁ":       "Enel CE",
    "ENEL CEARA":       "Enel CE",
    "ENEL GOIÁS":       "Enel GO",
    "ENEL GOIAS":       "Enel GO",
    "ENEL RIO":         "Enel RJ",
    # nomes antigos/razões sociais que ainda aparecem nas faturas
    "ELETROPAULO":      "Enel SP",
    "COELCE":           "Enel CE",
    "AMPLA":            "Enel RJ",
    "BANDEIRANTE":      "EDP SP",
    "ESCELSA":          "EDP ES",
    "CELG":             "Equatorial GO",
    "CEMAR":            "Equatorial MA",
    "CELPA":            "Equatorial PA",
    "CEPISA":           "Equatorial PI",
    "CEEE":             "Equatorial CEEE",
    "SUL-SUDESTE":      "Energisa Sul Sudeste",
    "SUL SUDESTE":      "Energisa Sul Sudeste",
}

# Palavras ignoradas no matching por palavras-chave
_SKIP = {
    "DE", "DO", "DA", "DOS", "DAS", "E", "S", "A", "SA", "LTDA",
    "DISTRIBUIDORA", "ENERGIA", "ENERGIAS", "ELETRICA", "ELÉTRICA",
    "ELETRICIDADE", "COMPANHIA", "SERVICOS", "SERVIÇOS", "DIS",
}


# Raiz do CNPJ (8 primeiros dígitos) da distribuidora → nome da lista.
# É o identificador mais confiável da fatura: o nome impresso varia
# ("EDP SP DISTRIB DE ENERGIA SA", "ENERGISA MATO GROSSO DO SUL - DISTR. ...")
# e grupos como Energisa/Enel/EDP têm uma distribuidora por estado.
# Conferidos nos cabeçalhos das faturas de 08/2026.
CNPJ_RAIZ = {
    "07282377": "Energisa Sul Sudeste",
    "03467321": "Energisa MT",
    "15413826": "Energisa MS",
    "25086034": "Energisa TO",
    "02302100": "EDP SP",
    "28152650": "EDP ES",
    "07047251": "Enel CE",
    "06981180": "Cemig-D",
    "04368898": "Copel-DIS",
    "08336783": "Celesc-DIS",
    "02016440": "RGE",
    "15139629": "Neoenergia Coelba",
    "02328280": "Neoenergia Elektro",
}

# Nome do estado por extenso → UF, para desempatar grupos com uma
# distribuidora por estado quando a UF não vem separada.
# Ordem importa: nomes compostos antes dos contidos neles.
_UF_POR_EXTENSO = [
    ("MATO GROSSO DO SUL", "MS"), ("MATO GROSSO", "MT"),
    ("RIO GRANDE DO SUL", "RS"), ("RIO GRANDE DO NORTE", "RN"),
    ("RIO DE JANEIRO", "RJ"), ("ESPIRITO SANTO", "ES"), ("ESPÍRITO SANTO", "ES"),
    ("SAO PAULO", "SP"), ("SÃO PAULO", "SP"), ("MINAS GERAIS", "MG"),
    ("SANTA CATARINA", "SC"), ("TOCANTINS", "TO"), ("RONDONIA", "RO"),
    ("RONDÔNIA", "RO"), ("SERGIPE", "SE"), ("PARAIBA", "PB"), ("PARAÍBA", "PB"),
    ("PARANA", "PR"), ("PARANÁ", "PR"), ("PARA", "PA"), ("PARÁ", "PA"),
    ("ACRE", "AC"), ("CEARA", "CE"), ("CEARÁ", "CE"), ("GOIAS", "GO"),
    ("GOIÁS", "GO"), ("MARANHAO", "MA"), ("MARANHÃO", "MA"), ("PIAUI", "PI"),
    ("PIAUÍ", "PI"), ("ALAGOAS", "AL"), ("AMAPA", "AP"), ("AMAPÁ", "AP"),
    ("PERNAMBUCO", "PE"), ("BAHIA", "BA"), ("AMAZONAS", "AM"), ("RORAIMA", "RR"),
]
_UFS = {c["estado"] for c in CONCESSIONARIAS}


def _uf_no_nome(n: str):
    """Procura a UF no próprio nome ("EDP SP ...", "ENERGISA TOCANTINS ...")."""
    for extenso, uf in _UF_POR_EXTENSO:
        if re.search(rf"\b{extenso}\b", n):
            return uf
    for tok in re.findall(r"\b[A-Z]{2}\b", n):
        if tok in _UFS:
            return tok
    return None


def normalizar_distribuidora(nome: str, uf: str = None, cnpj: str = None) -> str:
    """Converte o nome oficial extraído do PDF para o nome curto da lista.

    `cnpj` (da distribuidora) decide sozinho quando conhecido. `uf` desempata
    nomes que casam com várias distribuidoras do mesmo grupo (Energisa, Enel,
    EDP...). Na dúvida, devolve o nome original em vez de chutar."""
    raiz = re.sub(r"\D", "", cnpj or "")[:8]
    if raiz in CNPJ_RAIZ:
        return CNPJ_RAIZ[raiz]
    if not nome:
        return nome
    n = nome.upper()
    uf = (uf or "").strip().upper() or _uf_no_nome(n)

    # 1) Correspondência exata (case-insensitive)
    for c in CONCESSIONARIAS:
        if c["nome"].upper() == n:
            return c["nome"]

    # 2) Aliases explícitos (palavra inteira) — descartado se contradiz a UF
    for alias, nome_curto in _ALIASES.items():
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", n):
            estados = {c["estado"] for c in CONCESSIONARIAS if c["nome"] == nome_curto}
            if not uf or uf in estados:
                return nome_curto

    # 3) Matching por palavras significativas da lista
    #    Usa score: fração das palavras do nome da lista presentes no extraído
    best_score, empatados = 0, []
    for c in CONCESSIONARIAS:
        palavras = [w.upper().strip(".-") for w in c["nome"].split()
                    if len(w) > 2 and w.upper() not in _SKIP]
        if not palavras:
            continue
        hits = sum(1 for p in palavras if re.search(rf"\b{re.escape(p)}\b", n))
        score = hits / len(palavras)
        if score > best_score:
            best_score, empatados = score, [c]
        elif score == best_score and score > 0:
            empatados.append(c)

    if best_score >= 0.5:
        nomes = {c["nome"] for c in empatados}
        if len(nomes) == 1:
            return nomes.pop()
        # Empate (ex.: "ENERGISA" casa com todas as Energisa): desempata pela UF
        if uf:
            do_uf = {c["nome"] for c in empatados if c["estado"] == uf}
            if len(do_uf) == 1:
                return do_uf.pop()

    return nome  # fallback: mantém o nome original
