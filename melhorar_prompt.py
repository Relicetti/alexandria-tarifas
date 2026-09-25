"""
Aprende com o feedback de correções e mantém uma lista de REGRAS APRENDIDAS
que é anexada ao PROMPT base de extração (ver extrator._carregar_prompt).
Chamado em background após cada fatura salva com divergências.

A IA não reescreve mais o PROMPT inteiro: ele tem ~20 mil caracteres e a
resposta saía truncada, apagando metade das instruções. Agora ela só devolve
a lista de regras atualizada, que é curta e é validada antes de ser gravada.

As regras ficam em APRENDIZADOS_FILE, no volume persistente (/data) — não no
.py — para sobreviver a redeploys.
"""

import json
import os
import re
import threading
import traceback
import anthropic
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

import db as _db
import extrator as _extrator
_DATA_DIR         = Path(_db.DB_PATH).parent
FEEDBACK_FILE     = _DATA_DIR / "feedback_extracao.jsonl"
DEBUG_LOG         = _DATA_DIR / "debug_feedback.log"
APRENDIZADOS_FILE = _extrator.APRENDIZADOS_FILE

# Acima disso a lista virou um segundo prompt — sinal de resposta degenerada.
_MAX_CHARS_APRENDIZADOS = 12000

# Várias faturas salvas em sequência disparam várias threads; sem o lock uma
# sobrescreveria o resultado da outra.
_lock = threading.Lock()

PROMPT_MELHORIA = """Você é um engenheiro de prompts especialista em extração de dados de faturas de energia elétrica brasileiras.

O sistema usa o PROMPT BASE abaixo para extrair dados de PDFs via IA. Ao final dele é anexada uma lista de REGRAS APRENDIDAS com correções feitas pelo usuário.

PROMPT BASE (somente para contexto — NÃO reescreva):
\"\"\"
{prompt_base}
\"\"\"

REGRAS APRENDIDAS ATUAIS:
\"\"\"
{aprendizados}
\"\"\"

Houve {n} caso(s) recentes em que a extração retornou valores incorretos e o usuário corrigiu manualmente (extraído → corrigido; "None" significa campo vazio):
{casos}

Atualize a lista de REGRAS APRENDIDAS para que esses erros não se repitam:
- Mantenha as regras atuais que continuam válidas; ajuste ou funda as que se sobrepõem; remova as que contradizem correções mais recentes
- Cada regra deve ser específica e acionável: diga a distribuidora/grupo, o campo, onde o valor aparece na fatura e o que fazer (ex: sinal, linha certa, unidade)
- Não repita o que o PROMPT BASE já diz, a menos que a regra precise ser reforçada por causa de um erro recorrente
- Se uma correção parecer um ajuste pontual do usuário e não um erro de leitura da fatura, não crie regra para ela
- Não altere o formato JSON de saída nem os nomes dos campos
- No máximo 40 regras, uma por linha, cada linha começando com "- "
- Retorne APENAS a lista de regras (sem título, sem markdown, sem explicações, sem ```)
"""


def _log(msg: str):
    print(f"[melhorar_prompt] {msg}")
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [melhorar_prompt] {msg}\n")
    except Exception:
        pass


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


def _formatar_casos(casos: list) -> str:
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
    return "\n".join(linhas)


def _validar(texto: str) -> str | None:
    """Devolve o motivo de rejeição, ou None se a lista está boa pra gravar."""
    if not texto:
        return "resposta vazia"
    if len(texto) > _MAX_CHARS_APRENDIZADOS:
        return f"resposta grande demais ({len(texto)} chars)"
    regras = [l for l in texto.splitlines() if l.strip().startswith("-")]
    if not regras:
        return "resposta sem nenhuma regra no formato '- ...'"
    return None


def melhorar():
    with _lock:
        try:
            _melhorar()
        except Exception as e:
            _log(f"ERRO: {e}\n{traceback.format_exc()}")


def _melhorar():
    casos = _carregar_feedback_recente()
    if not casos:
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        _log("ANTHROPIC_API_KEY não configurada")
        return

    aprendizados = _extrator._carregar_aprendizados()

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": PROMPT_MELHORIA.format(
                prompt_base=_extrator._PROMPT_BASE,
                aprendizados=aprendizados or "(nenhuma ainda)",
                n=len(casos),
                casos=_formatar_casos(casos),
            ),
        }],
    )

    # Resposta cortada por limite de tokens é justamente o bug que apagava o
    # prompt — nunca grava nada que não terminou normalmente.
    if msg.stop_reason != "end_turn":
        _log(f"resposta descartada: stop_reason={msg.stop_reason}")
        return

    novo = msg.content[0].text.strip()
    # Remove markdown fences se o modelo as incluiu mesmo assim
    novo = re.sub(r"^```[^\n]*\n?", "", novo)
    novo = re.sub(r"\n?```$", "", novo).strip()

    motivo = _validar(novo)
    if motivo:
        _log(f"resposta descartada: {motivo}")
        return

    APRENDIZADOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = APRENDIZADOS_FILE.with_suffix(".tmp")
    tmp.write_text(novo + "\n", encoding="utf-8")
    tmp.replace(APRENDIZADOS_FILE)   # troca atômica: extração nunca lê arquivo pela metade

    n_regras = sum(1 for l in novo.splitlines() if l.strip().startswith("-"))
    _log(f"✅ {n_regras} regra(s) aprendida(s) gravadas com base em {len(casos)} caso(s) de correção.")
