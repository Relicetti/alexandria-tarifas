import os
import base64
import json
import re
import anthropic
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

_PROMPT_BASE = """Você está analisando uma fatura de energia elétrica brasileira de um sistema de geração distribuída (GD solar).

Extraia os dados abaixo e retorne SOMENTE um JSON válido, sem texto adicional.

{
  "distribuidora": "nome da concessionária EXATAMENTE como aparece na LISTA DE CONCESSIONÁRIAS no fim deste prompt",
  "distribuidora_nome_fatura": "razão social da distribuidora como impressa na fatura",
  "distribuidora_cnpj": "CNPJ da DISTRIBUIDORA (emitente da nota, no cabeçalho) — NÃO o do cliente" ou null,
  "uf": "UF (2 letras) do endereço da unidade consumidora",
  "tipo_gd": "GD1 ou GD2",
  "gd_evidencia": "trecho EXATO da fatura que indicou o tipo_gd (ex: 'Energia Atv Injetada GDII')" ou null,
  "instalacao": "número da instalação/UC (apenas dígitos)",
  "mes_referencia": "YYYY-MM (mês de competência/referência da fatura)",
  "data_leitura_anterior": "YYYY-MM-DD (data da leitura anterior do medidor)" ou null,
  "data_leitura_atual": "YYYY-MM-DD (data da leitura atual do medidor)" ou null,
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

  "aliquota_icms_pct": número (alíquota ICMS EM PERCENTUAL, como impressa — ex: 18,00 → 18.0) ou null,
  "valor_icms": número (valor ICMS em R$) ou 0,
  "aliquota_pis_pct": número (alíquota PIS/PASEP EM PERCENTUAL, como impressa — ex: 1,6500 → 1.65) ou null,
  "valor_pis": número (valor PIS em R$) ou 0,
  "aliquota_cofins_pct": número (alíquota COFINS EM PERCENTUAL, como impressa — ex: 7,6000 → 7.6) ou null,
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

  "celesc_itens": [ {"codigo": "0P", "descricao": "Consumo TE", "kwh": 150.0, "preco": 0.401133, "valor": 60.17, "icms": 12.0}, ... ] ou null — SÓ para CELESC (ver instruções),
  "celesc_subtotal": número (o primeiro "SUBTOTAL" do quadro de itens) ou null — SÓ para CELESC,

  "enel_te_consumida_faturada": número (Preço unit. da linha "Energia Consumida Faturada TE") ou null — SÓ Enel GD1 c/ múltiplos meses de compensação,
  "enel_tusd_consumida_faturada": número (Preço unit. da linha "Energia Consumida Faturada TUSD") ou null — idem,
  "enel_te_fornecida": número (Preço unit. da linha "Energia Ativa Fornecida TE") ou null — idem,
  "enel_tusd_fornecida": número (Preço unit. da linha "Energia Ativa Fornecida TUSD") ou null — idem,
  "enel_te_inj_media_ponderada": número (média ponderada por kWh, com sinal negativo, das linhas "Energia Atv Inj TE oUC .../...") ou null — idem,
  "enel_tusd_inj_media_ponderada": número (idem para as linhas "Energia Atv Inj TUSD oUC .../...") ou null — idem,

  "grupo": "um de: GER | EQT | NEOENERGIA | ENERGISA | LIGHT | CEMIG | BRASILIA"
}

Instruções:
- instalacao: procure por "Nº da Instalação", "UC", "Código de instalação" — retorne apenas os dígitos
- mes_referencia: procure por "Mês de referência", "Competência", "Período" — formato YYYY-MM
- data_leitura_anterior / data_leitura_atual: datas do período de leitura do medidor
  ("Leitura Anterior" / "Leitura Atual", "Datas de Leituras", "Período de consumo 08/07/2026 a 06/08/2026",
  "09/07/2026 a 06/08/2026 29 dias"). Converta DD/MM/AAAA → AAAA-MM-DD.
  NÃO use a "Próxima Leitura", a data de emissão nem o vencimento.
- consumo_kwh: kWh totais consumidos (pode aparecer como "Consumo faturado")
- injetada_kwh: energia injetada/compensada pelo sistema GD solar

- Concessionária (distribuidora / distribuidora_cnpj / uf):
  * distribuidora_cnpj = CNPJ impresso junto à razão social da distribuidora no cabeçalho
    ou no "Beneficiário" do boleto. NUNCA use o CNPJ/CPF do cliente.
  * Grupos com uma distribuidora por estado (Energisa, Enel, EDP, Equatorial, Neoenergia,
    CPFL) — escolha pelo estado da própria distribuidora: ENERGISA MATO GROSSO → "Energisa MT",
    ENERGISA MATO GROSSO DO SUL → "Energisa MS", ENERGISA SUL-SUDESTE → "Energisa Sul Sudeste",
    ENERGISA TOCANTINS → "Energisa TO", EDP SP → "EDP SP", EDP ES → "EDP ES",
    RGE SUL DISTRIBUIDORA → "RGE", CEEE Equatorial → "Equatorial CEEE".
  * Se nenhuma concessionária da lista corresponder, devolva a razão social impressa.

- Impostos (aliquota_*_pct / valor_*):
  Quase toda fatura tem um QUADRO DE TRIBUTOS separado, com colunas
  "Tributo | Base de cálculo (R$) | Alíquota (%) | Valor (R$)" e linhas ICMS, PIS (ou PIS/PASEP, PASEP)
  e COFINS. Leia as alíquotas DESSE quadro, no formato percentual impresso:
    "PIS 91,04 1,6500 1,50"  → aliquota_pis_pct = 1.65,  valor_pis = 1.50
    "COFINS 91,04 7,6000 6,92" → aliquota_cofins_pct = 7.6, valor_cofins = 6.92
    "ICMS 198,48 18,00 35,72"  → aliquota_icms_pct = 18.0,  valor_icms = 35.72
  * Informe a alíquota mesmo quando a base ou o valor forem 0 (isenção) — a alíquota impressa continua valendo.
  * Se houver MAIS DE UMA linha de ICMS (faixas, ex: 12% e 17%), use a alíquota da linha
    com a MAIOR base de cálculo, e valor_icms = soma dos valores de ICMS.
  * Se o quadro tiver linhas com base negativa (estorno, ex: EDP "PIS 142,11- 1,100-"), ignore-as
    para a alíquota; valor = soma algébrica das linhas.
  * Se não houver quadro, use a coluna "Alíquota ICMS (%)" dos itens de consumo, e para PIS/COFINS
    procure a mensagem de alíquotas do mês. Se não achar, deixe null (não invente).

- Tipo de GD (tipo_gd / gd_evidencia) — GD1 = geração anterior à Lei 14.300 (direito adquirido),
  GD2 = geração nova, com cobrança gradual do Fio B. Procure nas linhas de energia injetada/compensada
  e nas mensagens da fatura, NESTA ORDEM:
  1) Marcador explícito de GD2: "GDII", "GD II", "GD_II", "GD2", "G2" (ex: "El oUC Me TE G2"),
     "Parc. Inj. s/ Desc. - GD2", "Ajuste GDII", "classificada como GD_II" → tipo_gd = "GD2"
  2) Marcador explícito de GD1: "GDI", "GD I", "GDI-I", "GD1", "G1-Comp", "Energia compensada GD I" → "GD1"
     ATENÇÃO: "GDI" é GD1 e "GDII" é GD2 — confira se há um ou dois "I".
  3) Sem marcador (comum em EDP, RGE, Light, Coelba, CEEE): compare a TUSD da energia
     injetada/compensada com a TUSD do consumo. No GD2 o Fio B não é compensado, então a TUSD
     compensada fica BEM MENOR (tipicamente 20–50% menor) → "GD2". Se forem praticamente
     iguais → "GD1". Itens "Benefício Tarifário Bruto/Líquido" também indicam GD2.
  * "Lei 14.300" sozinho NÃO indica GD2 — aparece também em faturas GD1.
  * gd_evidencia = o trecho exato em que se baseou (a linha com o marcador, ou "TUSD comp 0,3374 vs consumo 0,4567").

- Para faturas CELESC (qualquer tipo — GD1, GD2, local, remota, com ou sem 0Q/0T):
  NÃO calcule tarifas. Transcreva em celesc_itens TODAS as linhas do quadro de itens faturados,
  na ordem, até o primeiro "SUBTOTAL" (exclusive). Cada linha começa com um código entre
  parênteses — (0P), (0Q), (0R), (0S), (0T), (12), (13), (6U), (73), (75), (76)... — e tem as colunas
  "Quant. | Preço unit. c/ trib. | Valor R$ | PIS/COFINS | Base ICMS | ICMS % | ICMS R$ | Tarifa s/ trib.".
  * codigo    = o código sem parênteses ("0P", "12", "6U")
  * descricao = o texto da linha, como impresso ("EI oUC Ma TE G2", "En Injetad TE")
  * kwh       = a quantidade (0 se não houver)
  * preco     = "Preço unit." (c/ trib.), COM o sinal impresso
  * valor     = "Valor R$", COM o sinal impresso (créditos são negativos)
  * icms      = "ICMS %" da linha (ex: 12, 17 ou 0)
  Copie os números EXATAMENTE como impressos — NUNCA corrija ICMS, some faixas ou junte linhas
  repetidas: cada faixa de ICMS é uma linha separada. celesc_subtotal = valor do primeiro SUBTOTAL.
  As tarifas (te_/tusd_), consumo_kwh, injetada_kwh e tipo_gd são recalculados em Python a partir
  dessas linhas; preencha-os com sua melhor leitura mesmo assim. grupo = "GER".

- Para faturas Enel (CE/GO/RJ/SP) GD1 Geração Compartilhada com MAIS DE UMA linha
  "Energia Atv Inj TE/TUSD oUC MM/YYYY ... GD1" (créditos de compensação vindos de
  meses de competência diferentes, cada um com sua própria tarifa):
  Preencha os campos brutos abaixo (além dos te_/tusd_ finais, que serão recalculados):
  * enel_te_consumida_faturada   = Preço unit. da linha "Energia Consumida Faturada TE"
  * enel_tusd_consumida_faturada = Preço unit. da linha "Energia Consumida Faturada TUSD"
  * enel_te_fornecida    = Preço unit. da linha "Energia Ativa Fornecida TE"
  * enel_tusd_fornecida  = Preço unit. da linha "Energia Ativa Fornecida TUSD"
  * enel_te_inj_media_ponderada   = Σ(kWh_linha × preço_unit_linha) / Σ(kWh_linha), somando TODAS
    as linhas "Energia Atv Inj TE oUC .../..." — mantenha o preço unitário COM O SINAL NEGATIVO
    exatamente como aparece na fatura (ex: "0,34946-" → -0,34946)
  * enel_tusd_inj_media_ponderada = idem, para as linhas "Energia Atv Inj TUSD oUC .../..."

  FÓRMULA FINAL (recalculada em Python, não confie na sua própria conta):
    te_compensada   = enel_te_consumida_faturada   − enel_te_fornecida   − enel_te_inj_media_ponderada
    tusd_compensada = enel_tusd_consumida_faturada − enel_tusd_fornecida − enel_tusd_inj_media_ponderada

  Exemplo (Enel CE GD1 Geração Compartilhada, 08/2026):
      Energia Consumida Faturada TE = 0,34733  |  Energia Ativa Fornecida TE = 0,34804
      Energia Atv Inj TE oUC 06/2026: 10 kWh × -0,35300
      Energia Atv Inj TE oUC 07/2026: 168 kWh × -0,34946
      enel_te_inj_media_ponderada = (10×-0,35300 + 168×-0,34946) / 178 = -0,349659
      te_compensada = 0,34733 − 0,34804 − (−0,349659) = 0,348949

      Energia Consumida Faturada TUSD = 0,65200  |  Energia Ativa Fornecida TUSD = 0,65168
      Energia Atv Inj TUSD oUC 06/2026: 10 kWh × -0,53100
      Energia Atv Inj TUSD oUC 07/2026: 168 kWh × -0,52375
      enel_tusd_inj_media_ponderada = (10×-0,53100 + 168×-0,52375) / 178 = -0,524157
      tusd_compensada = 0,65200 − 0,65168 − (−0,524157) = 0,524477

  Se houver SÓ UMA linha "Energia Atv Inj TE/TUSD" (sem múltiplos meses de competência),
  NÃO preencha estes campos enel_* — use o padrão GER normal
  (te_compensada/tusd_compensada = preço unitário dessa linha única).

- Para faturas com MÚLTIPLAS FAIXAS DE ICMS no consumo (ex: CEEE — faixa 12% e faixa 17%; CELESC segue a regra própria acima):
  As linhas de "Consumo TE" e "Consumo TUSD" aparecem REPETIDAS com kWh e tarifas diferentes.
  Neste caso calcule a MÉDIA PONDERADA pelo kWh de cada faixa:
  * te_consumo   = Σ(kWh_faixa × preço_TE_faixa)   / Σ(kWh_faixa)   — use "Preço unit. c/ trib."
  * tusd_consumo = Σ(kWh_faixa × preço_TUSD_faixa) / Σ(kWh_faixa)   — use "Preço unit. c/ trib."
  * consumo_kwh  = soma total de kWh de todas as faixas de consumo TE (ou TUSD)
  Da mesma forma para as linhas de energia injetada/compensada com múltiplas faixas:
  * te_compensada   = Σ(kWh_inj × |preço_TE_inj|)   / Σ(kWh_inj)   — use valor absoluto da tarifa
  * tusd_compensada = Σ(kWh_inj × |preço_TUSD_inj|) / Σ(kWh_inj)
  * injetada_kwh = soma total dos kWh injetados
  Exemplo: TE faixa1=150kWh×0,377933 + faixa2=1240kWh×0,400726 → te_consumo=(56,69+496,90)/1390=0,398482
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

# ── Aprendizados das correções ─────────────────────────────────────────────
# melhorar_prompt.py grava aqui uma lista curta de regras aprendidas com as
# correções do usuário, que é ANEXADA ao _PROMPT_BASE (nunca o substitui).
# Assim o base continua vindo do código — melhorias feitas aqui chegam à
# produção — e uma resposta ruim da IA não tem como apagar o prompt inteiro.
# Fica no volume persistente (/data), então sobrevive a redeploys.
# (O antigo prompt_extrator_aprendido.txt, que substituía o base inteiro e
# saía truncado, é ignorado.)
_DATA_DIR = Path(os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "tarifas.db"))).parent
APRENDIZADOS_FILE = _DATA_DIR / "prompt_extrator_aprendizados.txt"

_CABECALHO_APRENDIZADOS = (
    "\n\n══════════════════════════════════════════════════════════════════\n"
    "REGRAS APRENDIDAS COM CORREÇÕES DO USUÁRIO (prevalecem sobre as regras acima em caso de conflito):\n"
)


def _carregar_aprendizados() -> str:
    try:
        if APRENDIZADOS_FILE.exists():
            return APRENDIZADOS_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _lista_concessionarias() -> str:
    from concessionarias import CONCESSIONARIAS
    nomes = sorted({f'{c["nome"]} ({c["estado"]})' for c in CONCESSIONARIAS})
    return (
        "\n\nLISTA DE CONCESSIONÁRIAS (use o nome sem a UF entre parênteses no campo distribuidora):\n"
        + "; ".join(nomes) + "\n"
    )


def _carregar_prompt() -> str:
    base = _PROMPT_BASE + _lista_concessionarias()
    aprendizados = _carregar_aprendizados()
    if aprendizados:
        return base + _CABECALHO_APRENDIZADOS + aprendizados
    return base


PROMPT = _carregar_prompt()


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


def _processar_enel_multi_mes(dados: dict) -> dict:
    """
    Recalcula te_compensada/tusd_compensada de forma DETERMINÍSTICA (em Python,
    não confiando na matemática da IA) para faturas Enel GD1 Geração
    Compartilhada com créditos de compensação vindos de MÚLTIPLOS meses de
    competência (linhas "Energia Atv Inj TE/TUSD oUC MM/YYYY"), cada um com
    sua própria tarifa.

    Fórmula: compensada = consumida_faturada − fornecida − média_ponderada(inj)
    onde média_ponderada(inj) usa os preços unitários das linhas de injeção
    COM SINAL NEGATIVO (como aparecem na fatura), ponderados pelo kWh de cada linha.
    """
    te_cf   = dados.get("enel_te_consumida_faturada")
    te_forn = dados.get("enel_te_fornecida")
    te_inj  = dados.get("enel_te_inj_media_ponderada")
    if te_cf is None or te_forn is None or te_inj is None:
        return dados  # não é o padrão Enel multi-mês — não mexe

    dados["te_compensada"] = round(float(te_cf) - float(te_forn) - float(te_inj), 6)

    tusd_cf   = dados.get("enel_tusd_consumida_faturada")
    tusd_forn = dados.get("enel_tusd_fornecida")
    tusd_inj  = dados.get("enel_tusd_inj_media_ponderada")
    if tusd_cf is not None and tusd_forn is not None and tusd_inj is not None:
        dados["tusd_compensada"] = round(float(tusd_cf) - float(tusd_forn) - float(tusd_inj), 6)

    return dados


def _data_iso(v):
    """'2026-08-06' ou '06/08/2026' → '2026-08-06'; qualquer outra coisa → None."""
    from datetime import date
    v = str(v or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", v) or re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", v)
    if not m:
        return None
    a, b, c = m.groups()
    ano, mes, dia = (a, b, c) if len(a) == 4 else (c, b, a)
    try:
        return date(int(ano), int(mes), int(dia)).isoformat()
    except ValueError:
        return None


def _processar_datas_leitura(dados: dict) -> dict:
    """Valida as datas de leitura; período invertido ou > 70 dias é descartado."""
    from datetime import date
    ant = _data_iso(dados.get("data_leitura_anterior"))
    atu = _data_iso(dados.get("data_leitura_atual"))
    if ant and atu and not (0 < (date.fromisoformat(atu) - date.fromisoformat(ant)).days <= 70):
        ant = atu = None
    dados["data_leitura_anterior"], dados["data_leitura_atual"] = ant, atu
    return dados


def _processar_aliquotas(dados: dict) -> dict:
    """
    Converte as alíquotas lidas em percentual (aliquota_*_pct, como impressas
    no quadro de tributos) para a fração usada no resto do app (0.18, 0.0165).
    Sem alíquota impressa mas com base e valor, calcula valor/base.
    """
    for imp in ("icms", "pis", "cofins"):
        pct = dados.pop(f"aliquota_{imp}_pct", None)
        try:
            pct = float(pct) if pct is not None else None
        except (TypeError, ValueError):
            pct = None
        if pct is not None and pct > 0:
            dados[f"aliquota_{imp}"] = round(pct / 100, 6)
        elif not dados.get(f"aliquota_{imp}"):
            dados[f"aliquota_{imp}"] = 0
    return dados


_RE_GD2 = re.compile(r"GD[\s_]?II\b|GD[\s_-]?2\b|\bG2\b|GD_II", re.I)
_RE_GD1 = re.compile(r"GD[\s_]?I\b|GDI-I|GD[\s_-]?1\b|\bG1\b", re.I)


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _processar_tipo_gd(dados: dict) -> dict:
    """
    Decide GD1/GD2 pelo trecho que a IA citou (gd_evidencia), que é mais
    confiável que a conclusão dela: "GDI" x "GDII" é fácil de confundir.
    Campos que só existem no GD2 também contam. Sem nada disso, fica com a
    resposta da IA; na falta dela, GD1.
    """
    evid = str(dados.get("gd_evidencia") or "")
    tipo = str(dados.get("tipo_gd") or "").upper().replace(" ", "")
    if _RE_GD2.search(evid):
        tipo = "GD2"
    elif _RE_GD1.search(evid):
        tipo = "GD1"
    elif _num(dados.get("scee_comp_nao_isento")) or _num(dados.get("ajuste_gd2")):
        tipo = "GD2"
    dados["tipo_gd"] = tipo if tipo in ("GD1", "GD2") else "GD1"
    return dados


def _processar_distribuidora(dados: dict) -> dict:
    from concessionarias import normalizar_distribuidora
    nome = dados.get("distribuidora") or dados.get("distribuidora_nome_fatura") or ""
    dados["distribuidora"] = normalizar_distribuidora(
        nome, uf=dados.get("uf"), cnpj=dados.get("distribuidora_cnpj"))
    return dados


# ── CELESC ────────────────────────────────────────────────────────────────────
# A IA só transcreve as linhas do quadro de itens (celesc_itens); as contas
# saem daqui, para todos os formatos (GD1/GD2, local/remota, com ou sem 0Q/0T).
_CELESC_CONSUMO = {"0P", "0Q", "0R"}          # linhas de TE com o kWh consumido
# (linhas de consumo, linhas da parte compensada, linha de crédito) por tarifa
_CELESC_LINHAS = {"te": ("0P", {"0Q", "0R"}, "12"), "tusd": ("0S", {"0T"}, "13")}


def _celesc_itens(dados: dict) -> list[dict]:
    itens = []
    for i in dados.get("celesc_itens") or []:
        if not isinstance(i, dict):
            continue
        cod = str(i.get("codigo") or "").strip("() ").upper()
        if cod:
            itens.append({"codigo": cod, "descricao": str(i.get("descricao") or ""),
                          "kwh": abs(_num(i.get("kwh"))), "preco": _num(i.get("preco")),
                          "valor": _num(i.get("valor")), "icms": _num(i.get("icms"))})
    return itens


def _celesc_preco_medio(itens: list[dict], codigos):
    """Preço unitário impresso, ponderado pelo kWh, das linhas com esses códigos
    (em módulo: o crédito da geração local vem com preço negativo)."""
    linhas = [i for i in itens if i["codigo"] in codigos and i["kwh"] > 0]
    total = sum(i["kwh"] for i in linhas)
    return sum(i["kwh"] * abs(i["preco"]) for i in linhas) / total if total else None


def _processar_celesc(dados: dict) -> dict:
    """
    Faturas CELESC: consumo, injetada, tipo de GD e as quatro tarifas saem das
    linhas transcritas, nunca da conta da IA.
      * consumo  = kWh de 0P + 0Q + 0R;  injetada = kWh das linhas (12)
      * tarifas pelos preços unitários impressos (sem correção de ICMS), cada
        um ponderado pelo kWh quando há mais de uma linha (faixas de ICMS):
        consumo    = preço de 0P (TE) / 0S (TUSD)
        compensada, com 0Q/0R/0T = consumo − (preço de 0Q+0R − preço de 12) na TE,
                                   consumo − (preço de 0T − preço de 13) na TUSD
        compensada, sem eles     = preço de 12 (TE) / 13 (TUSD)
      * tipo_gd = GD2 se alguma linha tem o marcador "G2"; senão GD1.
    Sem as linhas, a fatura fica com a leitura da IA.
    """
    if "celesc" not in (dados.get("distribuidora") or "").lower():
        return dados
    itens = _celesc_itens(dados)
    if not itens:
        return dados

    # Conferência da transcrição: a soma das linhas tem que bater com o SUBTOTAL.
    subtotal = dados.get("celesc_subtotal")
    if subtotal is not None:
        soma = sum(i["valor"] for i in itens)
        if abs(soma - _num(subtotal)) > 0.05:
            dados["_aviso_extracao"] = (
                f"Celesc: a soma das linhas lidas (R$ {soma:.2f}) não bate com o SUBTOTAL "
                f"da fatura (R$ {_num(subtotal):.2f}). Confira as tarifas.")

    def kwh(cods):
        return sum(i["kwh"] for i in itens if i["codigo"] in cods)

    consumo = kwh(_CELESC_CONSUMO)
    inj     = kwh({"12"})
    if consumo > 0:
        dados["consumo_kwh"] = round(consumo, 3)
    dados["injetada_kwh"] = round(inj, 3)
    dados["grupo"] = "GER"
    dados["scee_beneficio_bruto"] = dados["scee_beneficio_liquido"] = 0   # (6U)/(73) se anulam

    for pre, (cod, compensado, credito) in _CELESC_LINHAS.items():
        t = _celesc_preco_medio(itens, {cod})
        if t is None:
            continue
        dados[f"{pre}_consumo"] = round(t, 6)
        p_cred = _celesc_preco_medio(itens, {credito}) if inj else None
        p_comp = _celesc_preco_medio(itens, compensado)
        if p_cred is None:
            dados[f"{pre}_compensada"] = None
        elif p_comp is not None:
            dados[f"{pre}_compensada"] = round(t - (p_comp - p_cred), 6)
        else:
            dados[f"{pre}_compensada"] = round(p_cred, 6)

    # A Celesc marca com "G2" toda linha de GD2 — créditos (12)/(13) e benefício
    # tarifário (6U)/(73). Sem "G2" é GD1, inclusive a geração local sem marcador.
    gd2 = [i for i in itens if re.search(r"\bG2\b", i["descricao"])]
    gd1 = [i for i in itens if re.search(r"\bG1\b", i["descricao"])]
    if inj or gd2:
        dados["tipo_gd"] = "GD2" if gd2 else "GD1"
        ev = (gd2 or gd1)
        dados["gd_evidencia"] = f'({ev[0]["codigo"]}) {ev[0]["descricao"]}' if ev else "Celesc sem marcador G2"

    # Itens 0Q/0T (consumo compensado na própria fatura) ou geração local
    # (crédito sem "oUC" = de outra UC) indicam autoconsumo.
    local = any(i["codigo"] == "12" and "ouc" not in i["descricao"].lower() for i in itens)
    if kwh({"0Q", "0R", "0T"}) > 0 or local:
        dados["modalidade"] = "Autoconsumo"
    elif inj:
        dados["modalidade"] = "Geração Compartilhada"
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
        max_tokens=4096,
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
                {"type": "text", "text": _carregar_prompt()},
            ],
        }],
    )

    text = msg.content[0].text.strip()
    # Remove markdown fences se presentes
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    dados = json.loads(text)
    dados = _processar_distribuidora(dados)
    dados = _processar_aliquotas(dados)
    dados = _processar_datas_leitura(dados)
    dados = _processar_tipo_gd(dados)
    dados = _processar_celesc(dados)
    dados = _processar_enel_multi_mes(dados)
    dados = _processar_bandeiras(dados)
    return dados
