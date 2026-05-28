"""
Melhora automaticamente o PROMPT de extração com base no feedback de correções.
Chamado em background após cada fatura salva com divergências.
"""

import json
import os
import re
import anthropic
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

FEEDBACK_FILE = Path(__file__).parent / "feedback_extracao.jsonl"
EXTRATOR_FILE = Path(__file__).parent / "extrator.py"

PROMPT_MELHORIA = """Você é um engenheiro de prompts especialista em extração de dados de faturas de energia elétrica brasileiras.

O sistema usa o PROMPT abaixo para extrair dados de PDFs via IA.
Houve {n} caso(s) recentes onde a extração retornou valores incorretos — o usuário precisou corrigir os dados manualmente.

PROMPT ATUAL:
\"\"\"
{prompt_atual}
\"\"\"

CASOS COM ERROS (extraído → corrigido pelo usuário):
{casos}

Analise os erros e reescreva o PROMPT com melhorias PRECISAS E MÍNIMAS para que esses tipos de erros não ocorram novamente.
- Não altere partes do PROMPT que já funcionam bem
- Adicione ou ajuste apenas as instruções necessárias para cobrir os casos de erro acima
- Mantenha exatamente o mesmo formato JSON de saída e a mesma estrutura geral do PROMPT
- Se o erro foi num campo específico de uma distribuidora específica, adicione instrução clara para aquele caso
- Retorne APENAS o texto do novo PROMPT (sem markdown, sem explicações adicionais, sem ```)
"""


def _extrair_prompt_atual() -> str:
    texto = EXTRATOR_FILE.read_text(encoding="utf-8")
    m = re.search(r'PROMPT\s*=\s*"""(.*?)"""', texto, re.DOTALL)
    return m.group(1) if m else ""


def _atualizar_prompt(novo_prompt: str):
    texto = EXTRATOR_FILE.read_text(encoding="utf-8")
    # Escapa possíveis """ dentro do novo prompt
    novo_prompt_safe = novo_prompt.replace('"""', "'''")
    novo_texto = re.sub(
        r'(PROMPT\s*=\s*""").*?(""")',
        lambda m_: m_.group(1) + novo_prompt_safe + m_.group(2),
        texto,
        flags=re.DOTALL,
    )
    EXTRATOR_FILE.write_text(novo_texto, encoding="utf-8")


def _carregar_feedback_recente(max_casos: int = 15) -> list:
    if not FEEDBACK_FILE.exists():
        return []
    casos = []
    with open(FEEDBACK_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
                if c.get("diffs"):
                    casos.append(c)
            except Exception:
                pass
    return casos[-max_casos:]


def melhorar():
    casos = _carregar_feedback_recente()
    if not casos:
        return

    prompt_atual = _extrair_prompt_atual()
    if not prompt_atual:
        print("[melhorar_prompt] PROMPT não encontrado em extrator.py")
        return

    # Formata os casos de erro de forma legível
    linhas = []
    for i, caso in enumerate(casos, 1):
        linhas.append(
            f"Caso {i} — {caso.get('distribuidora', '?')} [{caso.get('grupo', '?')}] "
            f"({caso.get('ts', '')[:10]}):"
        )
        for campo, vals in caso.get("diffs", {}).items():
            linhas.append(
                f"  {campo}: extraído={vals['extraido']}  →  correto={vals['corrigido']}"
            )
    casos_txt = "\n".join(linhas)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[melhorar_prompt] ANTHROPIC_API_KEY não configurada")
        return

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": PROMPT_MELHORIA.format(
                n=len(casos),
                prompt_atual=prompt_atual,
                casos=casos_txt,
            ),
        }],
    )

    novo_prompt = msg.content[0].text.strip()
    # Remove markdown fences se o modelo as incluiu mesmo assim
    novo_prompt = re.sub(r"^```[^\n]*\n?", "", novo_prompt)
    novo_prompt = re.sub(r"\n?```$", "", novo_prompt)

    _atualizar_prompt(novo_prompt)
    print(
        f"[melhorar_prompt] ✅ PROMPT atualizado com base em {len(casos)} "
        f"caso(s) de correção."
    )
