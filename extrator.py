import os
import base64
import json
import re
import anthropic
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

PROMPT = """Você está analisando uma fatura de energia elétrica brasileira de um sistema de geração distribuída (GD solar).

Extraia os dados abaixo e retorne SOMENTE um JSON válido, sem texto adicional.

{
  "distribuidora": "nome da concessionária de energia",
  "instalacao": "número da instalação/UC (apenas dígitos)",
  "mes_referencia": "YYYY-MM (mês de competência/referência da fatura)",
  "consumo_kwh": número (kWh consumidos no período),
  "injetada_kwh": número (kWh injetados ou compensados pela GD, 0 se ausente),
  "valor_concessionaria": número (valor total da fatura em R$),

  "te_consumo": número (tarifa TE do consumo em R$/kWh) ou null,
  "tusd_consumo": número (TUSD do consumo em R$/kWh) ou null,
  "te_compensada": número (TE da energia compensada em R$/kWh) ou null,
  "tusd_compensada": número (TUSD da energia compensada em R$/kWh) ou null,

  "tarifa_distribuidora_input": número (tarifa unitária total distribuidora R$/kWh, quando TE+TUSD não separados) ou null,
  "tarifa_compensada_input": número (tarifa unitária da compensação R$/kWh) ou null,
  "ajuste_gd2": número (ajuste GD2 em R$) ou 0,

  "tusd_distribuidora": número (TUSD distribuidora — faturas NEOENERGIA) ou null,
  "te_distribuidora": número (TE distribuidora — faturas NEOENERGIA) ou null,
  "desconto_injecao": número (valor total do desconto de injeção em R$ — faturas NEOENERGIA) ou null,

  "scee_consumo": número (valor SCEE consumo em R$) ou null,
  "scee_injecao": número (valor SCEE injeção em R$) ou null,
  "scee_comp_nao_isento": número (valor SCEE compensação não isento em R$) ou null,
  "scee_beneficio_bruto": número (benefício bruto SCEE em R$) ou 0,
  "scee_beneficio_liquido": número (benefício líquido SCEE em R$) ou 0,

  "tusd_injetada_gd": número (TUSD injetada GD R$/kWh — faturas LIGHT) ou null,
  "te_injetada_gd": número (TE injetada GD R$/kWh — faturas LIGHT) ou null,
  "tusd_fornecida_gd": número (TUSD fornecida GD R$/kWh — faturas LIGHT) ou null,
  "te_fornecida_gd": número (TE fornecida GD R$/kWh — faturas LIGHT) ou null,

  "aliquota_icms": número (alíquota ICMS ex: 0.25) ou 0,
  "valor_icms": número (valor ICMS em R$) ou 0,
  "aliquota_pis": número (alíquota PIS ex: 0.0065) ou 0,
  "valor_pis": número (valor PIS em R$) ou 0,
  "aliquota_cofins": número (alíquota COFINS ex: 0.03) ou 0,
  "valor_cofins": número (valor COFINS em R$) ou 0,

  "b_amarela_cons_kwh": número ou 0,
  "b_amarela_cons_valor": número ou 0,
  "b_verm_p1_cons_kwh": número ou 0,
  "b_verm_p1_cons_valor": número ou 0,
  "b_verm_p2_cons_kwh": número ou 0,
  "b_verm_p2_cons_valor": número ou 0,
  "b_amarela_inj_kwh": número ou 0,
  "b_amarela_inj_valor": número ou 0,
  "b_verm_p1_inj_kwh": número ou 0,
  "b_verm_p1_inj_valor": número ou 0,
  "b_verm_p2_inj_kwh": número ou 0,
  "b_verm_p2_inj_valor": número ou 0,

  "grupo": "um de: GER | EQT | NEOENERGIA | ENERGISA | LIGHT | CEMIG | BRASILIA"
}

Instruções:
- instalacao: procure por "Nº da Instalação", "UC", "Código de instalação" — retorne apenas os dígitos
- mes_referencia: procure por "Mês de referência", "Competência", "Período" — formato YYYY-MM
- consumo_kwh: kWh totais consumidos (pode aparecer como "Consumo faturado")
- injetada_kwh: energia injetada/compensada pelo sistema GD solar

- Para faturas CELESC G2 (Geração Distribuída Remota — energia vinda de outra UC):
  Os itens da fatura seguem este padrão de códigos:
  * (0P) Consumo TE         — kWh residuais (com ICMS), preço inclui impostos
  * (0Q) Con TE Is I/P/C   — kWh compensados pela injeção GD2 (isentos ICMS/PIS/COFINS), mesmo preço unitário sem impostos
  * (0S) Consumo TUSD       — kWh residuais TUSD (com ICMS)
  * (0T) Con TUSD Is P/C    — kWh compensados TUSD (isentos PIS/COFINS), pode ter múltiplas faixas de ICMS
  * (12) El oUC Me TE G2    — CRÉDITO TE da energia injetada de outra UC (valor negativo)
  * (13) El oUC Me TU G2    — CRÉDITO TUSD da energia injetada de outra UC (valor negativo)
  * (6U) Ben Tar Brut G2    — Benefício tarifário bruto GD2 (diferença TUSD cobrada vs creditada)
  * (73) Ben Tar Líq G2     — Benefício tarifário líquido GD2 (mesmo valor negativo — cancela o (6U) nesta UC)

  DOIS SUBTIPOS de CELESC G2 — identifique pelo que aparece na fatura:

  ── SUBTIPO A: Autoconsumo (mesma UC) ──
  Fatura contém itens (0Q) e (0T) — são os kWh compensados dentro da própria UC.
  Estrutura: 0P + 0Q + 0S + 0T + 12 + 13 + 6U + 73

  REGRAS para CELESC G2 Autoconsumo:
  * consumo_kwh  = soma de TODOS os kWh (0P) + soma de todos os kWh (0Q)
  * injetada_kwh = kWh do item (12) ou (13) — são iguais
  * grupo = "GER"
  * ATENÇÃO: (0P) e (0S) podem aparecer em MÚLTIPLAS LINHAS (uma por faixa de ICMS).
    Sempre calcule a MÉDIA PONDERADA pelo kWh:
  * te_consumo_raw   = Σ(kWh_faixa_0P × preço_faixa_0P) / Σ(kWh_faixa_0P)
  * tusd_consumo_raw = Σ(kWh_faixa_0S × preço_faixa_0S) / Σ(kWh_faixa_0S)

  CORREÇÃO DE ICMS (para Autoconsumo):
  Se ICMS de (0P) = 12%: te_consumo   = te_consumo_raw   × (1 − 0,12) / (1 − 0,17)
  Se ICMS de (0P) = 17%: te_consumo   = te_consumo_raw   (usa como está)
  Se ICMS de (0S) = 12%: tusd_consumo = tusd_consumo_raw × (1 − 0,12) / (1 − 0,17)
  Se ICMS de (0S) = 17%: tusd_consumo = tusd_consumo_raw (usa como está)
  Quando (0P) ou (0S) tiver múltiplas linhas com ICMS diferentes, aplique a correção
  linha a linha antes de calcular a média ponderada.

  FÓRMULAS FINAIS (Autoconsumo):
  * valor_0q        = soma dos Valor R$ de todas as linhas (0Q)
  * valor_12        = soma dos Valor R$ de todas as linhas (12) — será negativo
  * valor_0t        = soma dos Valor R$ de TODAS as linhas (0T) — soma tudo, qualquer ICMS
  * valor_13        = soma dos Valor R$ de todas as linhas (13) — será negativo
  * te_compensada   = (injetada_kwh × te_consumo   − (valor_0q + valor_12)) / injetada_kwh
  * tusd_compensada = (injetada_kwh × tusd_consumo − (valor_0t + valor_13)) / injetada_kwh

  Exemplo Autoconsumo (08/2026 — ASSOCIACAO USINAS ALEXANDRIA II):
      injetada_kwh    = 140,610
      (0P) ICMS 12% → te_consumo_raw = 0,394947 → corrigido: 0,394947 × 0,88/0,83 = 0,418737
      (0S) ICMS 12% → tusd_consumo_raw = 0,458568 → corrigido: 0,458568 × 0,88/0,83 = 0,486193
      valor_0q = 45,27  |  valor_12 = -45,26  →  soma = 0,01
      valor_0t = 31,26 + 30,17 = 61,43  |  valor_13 = -41,35  →  soma = 20,08
      te_compensada   = (140,610 × 0,418737 − 0,01)  / 140,610 = 0,418666
      tusd_compensada = (140,610 × 0,486193 − 20,08) / 140,610 = 0,343414

  ── SUBTIPO B: Geração Compartilhada (outra UC) ──
  Fatura NÃO contém itens (0Q) nem (0T). Só há (0P), (0S), (12), (13), (6U), (73).
  O consumidor paga o consumo total em (0P)/(0S) e recebe crédito direto em (12)/(13).

  REGRAS para CELESC G2 Geração Compartilhada:
  * consumo_kwh  = kWh do item (0P)
  * injetada_kwh = kWh do item (12) ou (13) — são iguais
  * grupo = "GER"

  CORREÇÃO DE ICMS (para Geração Compartilhada):
  Aplica a mesma lógica: se ICMS de (0P)/(0S) for 12%, corrige para 17%.
  Se já for 17%, usa como está.
  Se ICMS de (0P) = 12%: te_consumo   = preço(0P) × (1 − 0,12) / (1 − 0,17)
  Se ICMS de (0P) = 17%: te_consumo   = preço(0P)
  Se ICMS de (0S) = 12%: tusd_consumo = preço(0S) × (1 − 0,12) / (1 − 0,17)
  Se ICMS de (0S) = 17%: tusd_consumo = preço(0S)

  FÓRMULAS FINAIS (Geração Compartilhada) — simples, pega direto da fatura:
  * te_compensada   = preço unitário do item (12)   (coluna "Preço unit." da linha 12)
  * tusd_compensada = preço unitário do item (13)   (coluna "Preço unit." da linha 13)

  Exemplo Geração Compartilhada (08/2026 — EPPLER E BONELLI):
      consumo_kwh  = 278,000  |  injetada_kwh = 256,597
      (0P) ICMS 17% → te_consumo   = 0,418921  (sem correção)
      (0S) ICMS 17% → tusd_consumo = 0,486295  (sem correção)
      te_compensada   = 0,321930  (preço unitário do item 12)
      tusd_compensada = 0,294104  (preço unitário do item 13)

- Para faturas CELESC G1 (geração local, sem injeção remota): usar o padrão GER normal
  (te_consumo + tusd_consumo separados, te_compensada + tusd_compensada, grupo = "GER")

- Para faturas com MÚLTIPLAS FAIXAS DE ICMS no consumo (ex: CELESC G1, CEEE — faixa 12% e faixa 17%):
  As linhas de "Consumo TE" e "Consumo TUSD" aparecem REPETIDAS com kWh e tarifas diferentes.
  Neste caso calcule a MÉDIA PONDERADA pelo kWh de cada faixa:
  * te_consumo   = Σ(kWh_faixa × preço_TE_faixa)   / Σ(kWh_faixa)   — use "Preço unit. c/ trib."
  * tusd_consumo = Σ(kWh_faixa × preço_TUSD_faixa) / Σ(kWh_faixa)   — use "Preço unit. c/ trib."
  * consumo_kwh  = soma total de kWh de todas as faixas de consumo TE (ou TUSD)
  Da mesma forma para as linhas de energia injetada/compensada com múltiplas faixas:
  * te_compensada   = Σ(kWh_inj × |preço_TE_inj|)   / Σ(kWh_inj)   — use valor absoluto da tarifa
  * tusd_compensada = Σ(kWh_inj × |preço_TUSD_inj|) / Σ(kWh_inj)
  * injetada_kwh = soma total dos kWh injetados
  Exemplo CELESC G1: TE faixa1=150kWh×0,377933 + faixa2=1240kWh×0,400726 → te_consumo=(56,69+496,90)/1390=0,398482
- Para faturas EQT — Equatorial (AL/MA/PA/PI/GO/CEEE/CEA):
  A fatura Equatorial tem linhas com colunas: kWh | Preço c/ tributos | Preço s/ tributos | coluna4 | coluna5 | Valor R$ total
  Use SEMPRE o "Valor R$ total" (última coluna numérica da linha), NUNCA as colunas intermediárias (PIS, COFINS, ICMS).
  * consumo_kwh = kWh da linha "Consumo (kWh)" + kWh da linha "Consumo Compensado (kWh)"  (total consumido)
  * injetada_kwh = kWh da linha "Consumo Compensado" ou "Energia Inj. oUC" (são iguais)
  * tarifa_distribuidora_input = Preço c/ tributos (2ª coluna) da linha "Consumo (kWh)"
    Exemplo: "Consumo (kWh) 162,29  1,152998  0,843180 ... 187,12" → tarifa_distribuidora_input = 1.152998
  * scee_consumo = Valor R$ total da linha "Consumo Compensado (kWh)" (positivo)
    Exemplo: "Consumo Compensado (kWh) 896,70  0,822572 ... 737,60" → scee_consumo = 737.60
  * scee_injecao = Valor R$ total da linha "Energia Inj. oUC" (NEGATIVO — crédito que cancela o consumo compensado)
    Exemplo: "Energia Inj. oUC 07/2026 mPT (kWh) 896,70 ... -737,60" → scee_injecao = -737.60
    (scee_consumo + scee_injecao ≈ 0, pois se cancelam)
  * scee_comp_nao_isento = Valor R$ total da linha "Parc. Inj. s/ Desc. - GD2" (positivo — cobrado sobre a injeção)
    Exemplo: "Parc. Inj. s/ Desc. - GD2 (kWh) 896,70 ... 241,24" → scee_comp_nao_isento = 241.24
  * scee_beneficio_bruto = Valor R$ total da linha "Benefício Tarifário Bruto SCEE" (último número da linha)
    Exemplo: "Benefício Tarifário Bruto SCEE 19,07 105,42 484,61" → scee_beneficio_bruto = 484.61
  * scee_beneficio_liquido = valor da linha "Benefício Tarifário Líquido SCEE" (NEGATIVO)
    Exemplo: "Benefício Tarifário Líquido SCEE -360,12" → scee_beneficio_liquido = -360.12
  Verificação: scee_comp_nao_isento + scee_beneficio_bruto + scee_beneficio_liquido deve ser positivo
    (= custo líquido da compensação para a distribuidora manter)

- Para faturas CEMIG: procure pelos itens SCEE na discriminação de serviços
- Para faturas LIGHT (Light S.A. — RJ):
  * consumo_kwh = coluna "Consumo kWh" da tabela do medidor (linha "Energia kWh" / "Tarifa Convencional")
    — NUNCA use o consumo líquido da seção GD; use sempre o consumo total do quadro de leitura do medidor
  * injetada_kwh = energia injetada/compensada da seção GD (quadro de compensação)
  * tarifa_distribuidora_input = tarifa unitária total R$/kWh cobrada sobre o consumo total de energia
    (ex: linha "Energia Elétrica", "Consumo de Energia Ativa", "Energia Ativa Fornecida" — é o preço unitário que multiplica pelos kWh totais consumidos)
    ATENÇÃO: essa tarifa inclui TUSD + TE + encargos; NÃO é tusd_fornecida_gd nem te_fornecida_gd
  * tusd_injetada_gd  = tarifa R$/kWh da linha "G1-Comp. TUSD GD" ou "TUSD Injetada GD" (preço unitário)
  * te_injetada_gd    = tarifa R$/kWh da linha "G1-Comp. TE GD"   ou "TE Injetada GD"   (preço unitário)
  * tusd_fornecida_gd = tarifa R$/kWh da linha "TUSD Fornecimento GD" ou "TUSD Fornecida GD" (preço unitário)
  * te_fornecida_gd   = tarifa R$/kWh da linha "TE Fornecimento GD"   ou "TE Fornecida GD"   (preço unitário)

- Para faturas NEOENERGIA (Coelba, Cosern, Pernambuco, Elektro):
  * tusd_distribuidora = tarifa R$/kWh da linha "Consumo-TUSD" (Preço Unitário do consumo)
  * te_distribuidora   = tarifa R$/kWh da linha "Consumo-TE"   (Preço Unitário do consumo)
  ATENÇÃO: as tarifas de consumo e de compensação SÃO DIFERENTES — use os valores corretos de cada linha

  Formato COSERN / Pernambuco (tem tarifas separadas por linha de compensação):
  * tusd_compensada = tarifa R$/kWh da linha "G1-Comp...-TUSD" (Preço Unitário da compensação TUSD)
  * te_compensada   = tarifa R$/kWh da linha "G1-Comp...-TE"   (Preço Unitário da compensação TE)
  * desconto_injecao = null (não preencher)

  Formato COELBA / Elektro (mostra um único valor total de desconto):
  * tusd_compensada = null
  * te_compensada   = null
  * desconto_injecao = valor total em R$ dos créditos de compensação GD (soma absoluta de todos os G1-Comp)

  * b_amarela_cons_valor = valor R$ do "Acrésc. Band. AMARELA" (cobrado no consumo, ex: 1,48)
  * b_amarela_inj_valor  = valor R$ do "G1-Acrésc.Bd.AM-Comp." (crédito da bandeira na injeção, ex: 0,95 — use valor absoluto/positivo)
- grupo: identifique pelo nome da concessionária e estrutura da fatura:
  * GER → CPFL, Copel, Enel (GO/CE/RJ/SP), EDP, RGE, Celesc, Energisa Sul Sudeste e demais com TE+TUSD separados
  * EQT → Equatorial (AL/MA/PA/PI/GO/CEEE/CEA) — tem 5 campos SCEE (consumo, injeção, comp. não isento, benefício bruto/líquido)
  * NEOENERGIA → Neoenergia Coelba/Cosern/Pernambuco/Elektro — tem crédito de desconto de injeção
  * ENERGISA → Energisa (AC/MT/MS/RO/SE/TO/PB/MR/NF) — tarifa distribuidora direta + tarifa compensada
  * LIGHT → Light (RJ) — tem TUSD/TE GD injetada e fornecida separados
  * CEMIG → Cemig-D (MG) — tem SCEE com 3 campos (consumo, injeção, comp. não isento)
  * BRASILIA → Neoenergia Brasília (DF) — tarifa distribuidora direta

- Bandeiras tarifárias: procure por QUALQUER UMA dessas denominações:
  * "Bandeira Tarifária Amarela", "Bandeira Tarifária Vermelha P1", "Bandeira Tarifária Vermelha P2"
  * "Adicional de Bandeira Amarela", "Adicional de Bandeira Vermelha P1", "Adicional de Bandeira Vermelha P2"
  * "Bandeira Amarela", "Bandeira Vermelha" (qualquer variação)
  * Qualquer linha que contenha a palavra "Bandeira" associada a Amarela, Vermelha P1 ou Vermelha P2

  REGRAS de preenchimento:
  * Se a fatura mostrar kWh e R$ separados para consumo e injeção → preencha todos os 4 campos (cons_kwh, cons_valor, inj_kwh, inj_valor)
  * Se a fatura mostrar apenas o VALOR TOTAL em R$ (sem kWh explícito, ou com kWh = quantidade líquida) → coloque o valor em b_X_cons_valor e deixe b_X_cons_kwh = 0
    (o sistema calculará automaticamente a tarifa e dividirá entre consumo e injeção)

  IMPORTANTE — lógica de extração:
  * b_X_cons_valor = valor em R$ cobrado pela bandeira sobre o CONSUMO (bruto, ex: 1,59)
  * b_X_inj_valor  = valor em R$ creditado pela bandeira sobre a INJEÇÃO (se existir linha separada, ex: 1,40)
  * b_X_cons_kwh   = kWh do consumo para bandeira (use 0 se não estiver explícito na fatura)
  * b_X_inj_kwh    = kWh da injeção para bandeira (use 0 se não estiver explícito)
  * Se aparecerem dois números iguais na mesma linha (ex: "1,59 1,59"), o primeiro é a tarifa unitária e o segundo é o valor total — use o SEGUNDO como b_X_cons_valor
  * NUNCA deixe b_X_cons_valor = 0 se houver qualquer cobrança de bandeira na fatura
"""


# Grupos que cobram bandeira no consumo BRUTO e creditam na injeção
# com a mesma tarifa unitária (cons_R$ / consumo_kWh).
# Para os demais grupos com campo de injeção (EQT, CEMIG), a bandeira
# é referenciada ao consumo líquido → usa divisor (consumo - injetado).
GRUPOS_BAND_BRUTO = {"GER"}


def _processar_bandeiras(dados: dict) -> dict:
    """
    Preenche os campos de bandeira de injeção a partir do valor de consumo
    extraído da fatura, quando injeção ainda está zerada.

    Lógica BRUTO (grupos em GRUPOS_BAND_BRUTO — ex: GER/CPFL):
        tarifa = cons_valor / consumo_total
        → cons_valor inalterado; inj_valor = tarifa × injetado

    Lógica LÍQUIDO (demais grupos com campo de injeção — ex: EQT, CEMIG):
        tarifa = cons_valor / (consumo - injetado)
        → distribui sobre consumo e injeção totais
    """
    consumo  = float(dados.get("consumo_kwh")  or 0)
    injetado = float(dados.get("injetada_kwh") or 0)
    grupo    = (dados.get("grupo") or "").upper()
    net      = consumo - injetado

    if consumo <= 0:
        return dados

    for tipo in ["amarela", "verm_p1", "verm_p2"]:
        cons_val = float(dados.get(f"b_{tipo}_cons_valor") or 0)
        inj_val  = float(dados.get(f"b_{tipo}_inj_valor")  or 0)

        if cons_val <= 0 or inj_val != 0:
            continue  # nada a fazer

        if grupo in GRUPOS_BAND_BRUTO:
            # Bandeira cobrada sobre consumo bruto; crédito proporcional na injeção
            tarifa = cons_val / consumo
            dados[f"b_{tipo}_cons_kwh"]  = round(consumo,  2)
            dados[f"b_{tipo}_cons_valor"] = round(cons_val, 2)     # inalterado
            dados[f"b_{tipo}_inj_kwh"]   = round(injetado, 2)
            dados[f"b_{tipo}_inj_valor"]  = round(tarifa * injetado, 2)
        elif net > 0:
            # Bandeira referenciada ao consumo líquido; distribui proporcionalmente
            tarifa = cons_val / net
            dados[f"b_{tipo}_cons_kwh"]  = round(consumo,  2)
            dados[f"b_{tipo}_cons_valor"] = round(tarifa * consumo,  2)
            dados[f"b_{tipo}_inj_kwh"]   = round(injetado, 2)
            dados[f"b_{tipo}_inj_valor"]  = round(tarifa * injetado, 2)

    return dados


def extrair_fatura(pdf_bytes: bytes) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "Variável ANTHROPIC_API_KEY não configurada. "
            "Defina-a com: set ANTHROPIC_API_KEY=sua-chave"
        )

    client = anthropic.Anthropic(api_key=api_key)
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": PROMPT},
            ],
        }],
    )

    text = msg.content[0].text.strip()
    # Remove markdown fences se presentes
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    dados = json.loads(text)
    dados = _processar_bandeiras(dados)
    return dados
