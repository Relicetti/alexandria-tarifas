"""
Motores de cálculo por grupo de concessionária.

Saídas comuns a todos os grupos:
  tarifa_distribuidora, tarifa_compensada,
  tarifa_geracao, desconto_real, desconto_ref (quando disponível)
"""

# ── helpers ──────────────────────────────────────────────────────────────────

def _g(d, *keys, default=0.0):
    for k in keys:
        v = d.get(k)
        if v is not None and v != '':
            return float(v)
    return default


def _saidas(tarifa_dist, tarifa_comp, tarifa_bruta_inj,
            conc_com, conc_sem, inj, consumo,
            desconto_base, desconto_ref_disponivel, desconto):
    """Calcula os 5 outputs finais a partir dos valores intermediários."""
    valor_geracao = (tarifa_bruta_inj - (tarifa_dist - tarifa_comp) * (1 - desconto)) * inj
    valor_fat_com = conc_sem if valor_geracao == 0 else conc_com + valor_geracao
    valor_fat_sem = conc_sem
    desconto_final = valor_fat_sem - valor_fat_com

    tarifa_geracao = valor_geracao / inj if inj else 0.0
    desconto_real  = desconto_final / valor_fat_sem if valor_fat_sem else 0.0
    desconto_ref   = desconto_base * inj / consumo if (consumo and desconto_ref_disponivel) else None

    return {
        "tarifa_distribuidora": round(tarifa_dist, 6),
        "tarifa_compensada":    round(tarifa_comp, 6),
        "tarifa_geracao":       round(tarifa_geracao, 6),
        "desconto_real":        round(desconto_real, 6),
        "desconto_ref":         round(desconto_ref, 6) if desconto_ref is not None else None,
    }


# ── cálculo de bandeira ───────────────────────────────────────────────────────

def _b_cons_kwh(d):
    """Bandeira consumo com kWh explícito (GER, EQT, CEMIG)."""
    kwh = _g(d,'b_amarela_cons_kwh') + _g(d,'b_verm_p1_cons_kwh') + _g(d,'b_verm_p2_cons_kwh')
    val = _g(d,'b_amarela_cons_valor') + _g(d,'b_verm_p1_cons_valor') + _g(d,'b_verm_p2_cons_valor')
    return val / kwh if kwh else 0.0

def _b_inj_kwh(d):
    """Bandeira injeção com kWh explícito (GER, EQT, CEMIG)."""
    kwh = _g(d,'b_amarela_inj_kwh') + _g(d,'b_verm_p1_inj_kwh') + _g(d,'b_verm_p2_inj_kwh')
    val = _g(d,'b_amarela_inj_valor') + _g(d,'b_verm_p1_inj_valor') + _g(d,'b_verm_p2_inj_valor')
    return val / kwh if kwh else 0.0

def _b_cons_val_only(d, denom):
    """Bandeira consumo apenas pelo valor (NEOENERGIA, ENERGISA, LIGHT, BRASÍLIA)."""
    val = _g(d,'b_amarela_cons_valor') + _g(d,'b_verm_p1_cons_valor') + _g(d,'b_verm_p2_cons_valor')
    return val / denom if denom else 0.0


# ── variantes de conc_com ─────────────────────────────────────────────────────

def _conc_A(consumo_residual, tarifa_dist, tarifa_comp, inj, tarifa_b_cons, tarifa_b_inj, consumo):
    """GER: inclui tarifa_b_inj."""
    return (consumo_residual * tarifa_dist
            + (tarifa_dist - tarifa_comp) * inj
            + tarifa_b_cons * consumo
            - inj * tarifa_b_inj)

def _conc_B(consumo_residual, tarifa_dist, tarifa_comp, inj, tarifa_b_cons):
    """EQT / CEMIG / ENERGISA / LIGHT / BRASÍLIA."""
    return (consumo_residual * (tarifa_dist + tarifa_b_cons)
            + (tarifa_dist - tarifa_comp) * inj)

def _conc_C(consumo, tarifa_dist, tarifa_comp, inj, tarifa_b_cons, tarifa_b_inj=0.0):
    """NEOENERGIA: inclui crédito de bandeira na injeção quando presente."""
    return tarifa_dist * consumo + tarifa_b_cons * consumo - tarifa_comp * inj - tarifa_b_inj * inj

def _conc_sem_std(consumo, tarifa_dist, tarifa_b_cons):
    return consumo * (tarifa_dist + tarifa_b_cons)


# ── funções públicas por grupo ────────────────────────────────────────────────

def calcular_GER(d):
    consumo = _g(d, 'consumo_kwh')
    inj     = _g(d, 'injetada_kwh')
    desc    = _g(d, 'desconto_aplicado')
    d_base  = _g(d, 'desconto_base')
    cobra   = bool(d.get('cobra_band'))

    tarifa_dist = _g(d,'te_consumo') + _g(d,'tusd_consumo')
    tarifa_comp = _g(d,'te_compensada') + _g(d,'tusd_compensada')
    tb_cons = _b_cons_kwh(d)
    tb_inj  = _b_inj_kwh(d)

    tarifa_bruta = (tarifa_dist + tb_cons if cobra else tarifa_dist) * (1 - desc)
    conc_com = _conc_A(consumo - inj, tarifa_dist, tarifa_comp, inj, tb_cons, tb_inj, consumo)
    conc_sem = _conc_sem_std(consumo, tarifa_dist, tb_cons)

    return _saidas(tarifa_dist, tarifa_comp, tarifa_bruta, conc_com, conc_sem,
                   inj, consumo, d_base, desconto_ref_disponivel=True, desconto=desc)


def calcular_EQT(d):
    consumo = _g(d, 'consumo_kwh')
    inj     = _g(d, 'injetada_kwh')
    desc    = _g(d, 'desconto_aplicado')
    d_base  = _g(d, 'desconto_base')
    cobra   = bool(d.get('cobra_band'))

    tarifa_dist = _g(d, 'tarifa_distribuidora_input')
    scee_group1 = _g(d,'scee_consumo') + _g(d,'scee_injecao')
    scee_group2 = (_g(d,'scee_comp_nao_isento') + _g(d,'scee_beneficio_bruto')
                   + _g(d,'scee_beneficio_liquido'))
    tarifa_comp = (tarifa_dist * inj - scee_group1 - scee_group2) / inj if inj else 0.0

    tb_cons = _b_cons_kwh(d)
    tb_inj  = _b_inj_kwh(d)

    tarifa_bruta = (tarifa_dist + tb_cons if cobra else tarifa_dist) * (1 - desc)
    conc_com = _conc_B(consumo - inj, tarifa_dist, tarifa_comp, inj, tb_cons)
    conc_sem = _conc_sem_std(consumo, tarifa_dist, tb_cons)

    return _saidas(tarifa_dist, tarifa_comp, tarifa_bruta, conc_com, conc_sem,
                   inj, consumo, d_base, desconto_ref_disponivel=True, desconto=desc)


def calcular_NEOENERGIA(d):
    consumo = _g(d, 'consumo_kwh')
    inj     = _g(d, 'injetada_kwh')
    desc    = _g(d, 'desconto_base')   # usa desconto_base direto
    cobra   = bool(d.get('cobra_band'))

    tarifa_dist = _g(d,'tusd_distribuidora') + _g(d,'te_distribuidora')
    # Cosern/Pernambuco: tarifas separadas; Coelba/Elektro: desconto total em R$
    if _g(d,'tusd_compensada') or _g(d,'te_compensada'):
        tarifa_comp = _g(d,'tusd_compensada') + _g(d,'te_compensada')
    else:
        tarifa_comp = _g(d,'desconto_injecao') / inj if inj else 0.0

    tb_cons = _b_cons_val_only(d, consumo)
    bi_val  = (_g(d,'b_amarela_inj_valor') + _g(d,'b_verm_p1_inj_valor')
               + _g(d,'b_verm_p2_inj_valor'))
    tb_inj  = bi_val / inj if inj else 0.0

    tarifa_bruta = (tarifa_dist + tb_cons if cobra else tarifa_dist) * (1 - desc)
    conc_com = _conc_C(consumo, tarifa_dist, tarifa_comp, inj, tb_cons, tb_inj)
    conc_sem = _conc_sem_std(consumo, tarifa_dist, tb_cons)

    return _saidas(tarifa_dist, tarifa_comp, tarifa_bruta, conc_com, conc_sem,
                   inj, consumo, desc, desconto_ref_disponivel=False, desconto=desc)


def calcular_ENERGISA(d):
    consumo = _g(d, 'consumo_kwh')
    inj     = _g(d, 'injetada_kwh')
    desc    = _g(d, 'desconto_aplicado')
    d_base  = _g(d, 'desconto_base')
    cobra   = bool(d.get('cobra_band'))
    consumo_residual = consumo - inj

    tarifa_dist = _g(d, 'tarifa_distribuidora_input')
    tarifa_comp = _g(d,'tarifa_compensada_input') - (_g(d,'ajuste_gd2') / inj if inj else 0)

    tb_cons = _b_cons_kwh(d)
    tb_inj  = _b_inj_kwh(d)

    tarifa_bruta = (tarifa_dist + tb_cons if cobra else tarifa_dist) * (1 - desc)
    conc_com = _conc_B(consumo_residual, tarifa_dist, tarifa_comp, inj, tb_cons)
    conc_sem = _conc_sem_std(consumo, tarifa_dist, tb_cons)

    return _saidas(tarifa_dist, tarifa_comp, tarifa_bruta, conc_com, conc_sem,
                   inj, consumo, d_base, desconto_ref_disponivel=True, desconto=desc)


def calcular_LIGHT(d):
    consumo = _g(d, 'consumo_kwh')
    inj     = _g(d, 'injetada_kwh')
    desc    = _g(d, 'desconto_aplicado')
    d_base  = _g(d, 'desconto_base')
    cobra   = bool(d.get('cobra_band'))
    consumo_residual = consumo - inj

    tarifa_dist_input = _g(d, 'tarifa_distribuidora_input')
    b_val = (_g(d,'b_amarela_cons_valor') + _g(d,'b_verm_p1_cons_valor')
             + _g(d,'b_verm_p2_cons_valor'))
    # LIGHT: bandeira extraída sobre consumo total (bruto) → divide por consumo
    tb_cons = b_val / consumo if consumo else 0.0

    # tarifa_dist líquida: input menos bandeira; tarifa_bruta reconstitui o input
    tarifa_dist = tarifa_dist_input - tb_cons
    fornecida_gd = _g(d,'tusd_fornecida_gd') + _g(d,'te_fornecida_gd')
    injetada_gd  = _g(d,'tusd_injetada_gd')  + _g(d,'te_injetada_gd')
    tarifa_comp  = tarifa_dist - (fornecida_gd - injetada_gd)

    tarifa_bruta = (tarifa_dist + tb_cons if cobra else tarifa_dist) * (1 - desc)
    conc_com = _conc_B(consumo_residual, tarifa_dist, tarifa_comp, inj, tb_cons)
    conc_sem = _conc_sem_std(consumo, tarifa_dist, tb_cons)

    return _saidas(tarifa_dist, tarifa_comp, tarifa_bruta, conc_com, conc_sem,
                   inj, consumo, d_base, desconto_ref_disponivel=True, desconto=desc)


def calcular_CEMIG(d):
    consumo = _g(d, 'consumo_kwh')
    inj     = _g(d, 'injetada_kwh')
    desc    = _g(d, 'desconto_base')   # usa desconto_base
    cobra   = bool(d.get('cobra_band'))

    tarifa_dist = _g(d, 'tarifa_distribuidora_input')
    scee_sum = _g(d,'scee_consumo') + _g(d,'scee_injecao') + _g(d,'scee_comp_nao_isento')
    tarifa_comp = (consumo * tarifa_dist - scee_sum) / consumo if consumo else 0.0

    tb_cons = _b_cons_kwh(d)
    tb_inj  = _b_inj_kwh(d)

    tarifa_bruta = (tarifa_dist + tb_cons if cobra else tarifa_dist) * (1 - desc)
    conc_com = _conc_B(consumo - inj, tarifa_dist, tarifa_comp, inj, tb_cons)
    conc_sem = _conc_sem_std(consumo, tarifa_dist, tb_cons)

    return _saidas(tarifa_dist, tarifa_comp, tarifa_bruta, conc_com, conc_sem,
                   inj, consumo, desc, desconto_ref_disponivel=False, desconto=desc)


def calcular_BRASILIA(d):
    consumo = _g(d, 'consumo_kwh')
    inj     = _g(d, 'injetada_kwh')
    desc    = _g(d, 'desconto_base')   # usa desconto_base
    cobra   = bool(d.get('cobra_band'))
    consumo_residual = consumo - inj

    tarifa_dist = _g(d, 'tarifa_distribuidora_input')
    tarifa_comp = _g(d,'tarifa_compensada_input') - (_g(d,'ajuste_gd2') / inj if inj else 0)

    tb_cons = _b_cons_val_only(d, consumo_residual)

    tarifa_bruta = (tarifa_dist + tb_cons if cobra else tarifa_dist) * (1 - desc)
    conc_com = _conc_B(consumo_residual, tarifa_dist, tarifa_comp, inj, tb_cons)
    conc_sem = _conc_sem_std(consumo, tarifa_dist, tb_cons)

    return _saidas(tarifa_dist, tarifa_comp, tarifa_bruta, conc_com, conc_sem,
                   inj, consumo, desc, desconto_ref_disponivel=False, desconto=desc)


# ── dispatcher ────────────────────────────────────────────────────────────────

_FUNCOES = {
    'GER':       calcular_GER,
    'EQT':       calcular_EQT,
    'NEOENERGIA': calcular_NEOENERGIA,
    'ENERGISA':  calcular_ENERGISA,
    'LIGHT':     calcular_LIGHT,
    'CEMIG':     calcular_CEMIG,
    'BRASILIA':  calcular_BRASILIA,
}


def calcular(grupo, dados):
    fn = _FUNCOES.get(grupo.upper())
    if not fn:
        raise ValueError(f"Grupo desconhecido: {grupo}")
    return fn(dados)


# ── config de campos por grupo (usado no formulário) ─────────────────────────

CAMPOS_GRUPO = {
    'GER': {
        'tarifa_dist':   'te_tusd',       # te_consumo + tusd_consumo
        'tarifa_comp':   'te_tusd',       # te_compensada + tusd_compensada
        'desconto':      'base_aplicado',
        'bandeira_cons': 'kwh_valor',
        'bandeira_inj':  'kwh_valor',
        'desconto_ref':  True,
    },
    'EQT': {
        'tarifa_dist':   'direto',
        'tarifa_comp':   'scee_5',
        'desconto':      'base_aplicado',
        'bandeira_cons': 'kwh_valor',
        'bandeira_inj':  'kwh_valor',
        'desconto_ref':  True,
    },
    'NEOENERGIA': {
        'tarifa_dist':   'tusd_te',
        'tarifa_comp':   'tusd_te_comp',
        'desconto':      'base',
        'bandeira_cons': 'valor',
        'bandeira_inj':  'nenhum',
        'desconto_ref':  False,
    },
    'ENERGISA': {
        'tarifa_dist':   'direto',
        'tarifa_comp':   'direto_ajuste',
        'desconto':      'base_aplicado',
        'bandeira_cons': 'kwh_valor',
        'bandeira_inj':  'kwh_valor',
        'desconto_ref':  True,
    },
    'LIGHT': {
        'tarifa_dist':   'direto',
        'tarifa_comp':   'tusd_te_4',
        'desconto':      'base_aplicado',
        'bandeira_cons': 'valor',
        'bandeira_inj':  'nenhum',
        'desconto_ref':  True,
    },
    'CEMIG': {
        'tarifa_dist':   'direto',
        'tarifa_comp':   'scee_3',
        'desconto':      'base',
        'bandeira_cons': 'kwh_valor',
        'bandeira_inj':  'kwh_valor',
        'desconto_ref':  False,
    },
    'BRASILIA': {
        'tarifa_dist':   'direto',
        'tarifa_comp':   'direto_ajuste',
        'desconto':      'base',
        'bandeira_cons': 'valor',
        'bandeira_inj':  'nenhum',
        'desconto_ref':  False,
    },
}
