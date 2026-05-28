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

- Para faturas com MÚLTIPLAS FAIXAS DE ICMS no consumo (ex: CELESC, CEEE — faixa 12% e faixa 17%):
  As linhas de "Consumo TE" e "Consumo TUSD" aparecem REPETIDAS com kWh e tarifas diferentes.
  Neste caso calcule a MÉDIA PONDERADA pelo kWh de cada faixa:
  * te_consumo   = Σ(kWh_faixa × preço_TE_faixa)   / Σ(kWh_faixa)   — use "Preço unit. c/ trib."
  * tusd_consumo = Σ(kWh_faixa × preço_TUSD_faixa) / Σ(kWh_faixa)   — use "Preço unit. c/ trib."
  * consumo_kwh  = soma total de kWh de todas as faixas de consumo TE (ou TUSD)
  Da mesma forma para as linhas de energia injetada/compensada com múltiplas faixas:
  * te_compensada   = Σ(kWh_inj × |preço_TE_inj|)   / Σ(kWh_inj)   — use valor absoluto da tarifa
  * tusd_compensada = Σ(kWh_inj × |preço_TUSD_inj|) / Σ(kWh_inj)
  * injetada_kwh = soma total dos kWh injetados
  Exemplo CELESC: TE faixa1=150kWh×0,377933 + faixa2=1240kWh×0,400726 → te_consumo=(56,69+496,90)/1390=0,398482
- Para faturas CEMIG/EQT: procure pelos itens SCEE na discriminação de serviços
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
